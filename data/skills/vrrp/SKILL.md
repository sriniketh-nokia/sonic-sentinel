---
name: sonic-vrrp
description: Debug SONiC VRRP (VRRPv4 and VRRPv6) issues end-to-end, from CONFIG_DB configuration through frrcfgd/vrrpmgrd, FRR vrrpd protocol state, vrrpsyncd, down to SAI/ASIC_DB programming in orchagent.
---

# SONiC VRRP Debugging

## State machine
                             +---------------+
                  +--------->|               |<-------------+
                  |          |  Initialize   |              |
                  |   +------|               |----------+   |
                  |   |      +---------------+          |   |
                  |   |                                 |   |
                  |   V                                 V   |
          +---------------+                       +---------------+
          |               |---------------------->|               |
          |    Master     |                       |    Backup     |
          |               |<----------------------|               |
          +---------------+                       +---------------+

## Architecture

VRRP config flows through two containers and five hops. Find which hop dropped the config instead of guessing.

| Hop | Component | Container | Role |
|---|---|---|---|
| 1 | `CONFIG_DB` `VRRP`/`VRRP6`/`VRRP_TRACK`/`VRRP6_TRACK` | — | YANG-validated source of truth |
| 2a | `frrcfgd` | `bgp` | Translates VRRP/VRRP6/VRRP_TRACK/VRRP6_TRACK rows into `vtysh` commands into FRR `vrrpd` (priority, adv-interval, version, shutdown, preempt, checksum, VIPs, `track-interface ... priority-dec ...`) |
| 2b | `vrrpmgrd` | `swss` | Creates the kernel `Vrrp4-<vrid>` / `Vrrp6-<vrid>` macvlan child interface on the parent, sets its admin state/VRF, adds the VIPs onto it at the kernel level (`ip link` / `ip addr`) |
| 3 | FRR `vrrpd` | `bgp` | Attaches to that macvlan, runs the VRRP state machine (Init→Backup/Master), toggles the macvlan's `protodown` based on the election result, sends/receives advertisements |
| 4 | `vrrpsyncd` | `swss` | Watches netlink link/addr events on `Vrrp*` interfaces, mirrors "VIP operationally active" into `APPL_DB` `VRRP_TABLE` |
| 5 | `orchagent` `VrrpOrch` | `swss` | Consumes `APPL_DB` `VRRP_TABLE`, programs a SAI router-interface (VRRP virtual MAC) + SAI route entry for the VIP into `ASIC_DB`/hardware. Lowest layer this skill covers. |

`frrcfgd` also runs a `VrrpStateSync` thread that polls `vtysh -c "show vrrp json"` / `"show vrrp6 json"` every 2s and republishes into `STATE_DB` `VRRP_STATE_TABLE` / `VRRP6_STATE_TABLE` — **only when priority/state actually change**, so `last_changed` reflects the last real transition, not the last poll.

`APPL_DB` uses one shared `VRRP_TABLE` for both v4 and v6 (no separate `VRRP6_TABLE`); `STATE_DB` splits into `VRRP_STATE_TABLE` / `VRRP6_STATE_TABLE`. Don't assume symmetry here.

## Step 1 — Configuration (CONFIG_DB)

```
sonic-db-cli CONFIG_DB hgetall "VRRP|<ifname>|<vrid>"
sonic-db-cli CONFIG_DB hgetall "VRRP6|<ifname>|<vrid>"
sonic-db-cli CONFIG_DB keys "VRRP_TRACK|<ifname>|<vrid>|*"
sonic-db-cli CONFIG_DB keys "VRRP6_TRACK|<ifname>|<vrid>|*"
```
Example:
```
$ sonic-db-cli CONFIG_DB hgetall "VRRP|Vlan100|2"
{'vrid': '2', 'vip@': '1.1.1.10'}
```
Leaf-list VIPs are stored as `vip@` (comma-separated if multiple), not `vip`.

Checks:
- Fields: `vrid`, `vip@`/`vip`, `priority` (1-254, default 100), `adv_interval` (default 1s), `preempt` (default enabled), `admin_status` (default up), `use_v2_checksum`, `version` (2 or 3).
- `accept_mode` and `virtual_link_local` are persisted in `CONFIG_DB` but `frrcfgd` explicitly skips programming them into FRR (logs a `WARNING`) — don't expect them to take effect.
- VIP must fall inside a subnet already on the parent interface (`ip addr show <ifname>` / `ip -6 addr show <ifname>`). `vrrpmgrd` derives the VIP's prefix length from the existing kernel address; if none covers it, it silently falls back to `/32` (`/128` for v6).
- Parent interface must be "ready" in `STATE_DB`: Vlan → `STATE_VLAN_TABLE|<name>`, PortChannel/sub-if → `STATE_LAG_TABLE|<name>`, physical port → `STATE_PORT_TABLE|<name>` field `state`. If not ready, `vrrpmgrd` pends silently — no error, just never applies.

## Step 2 — Show commands
If any of the command fails use `-h` flag and derive the command yourself.

```
show vrrp                              show vrrp6
show vrrp interface <ifname> <vrid>    show vrrp6 interface <ifname> <vrid>
show vrrp vrid <vrid>                  show vrrp6 vrid <vrid>
show vrrp summary                      show vrrp6 summary
```
Fast top-level check — the macvlan is a real L3 interface:
```
show ip interfaces   | grep -i "<ifname>\|Vrrp"
show ipv6 interfaces | grep -i "<ifname>\|Vrrp"
```
Example:
```
$ show ip int | grep -i Vlan
Vlan100    1.1.1.1/24     up/up   N/A   N/A
$ show ip int | grep -i Vrrp
Vrrp4-2    1.1.1.10/24    up/up   N/A   N/A
```

Full detail from the `bgp` container:
```
docker exec -it bgp vtysh -c "show vrrp"
docker exec -it bgp vtysh -c "show vrrp json"
docker exec -it bgp vtysh -c "show running-config"   # confirm 'vrrp <vrid> ...' under the interface stanza
docker exec -it bgp vtysh -c "show debugging vrrp"
```
Real `show vrrp` output (field names/order are ground truth — may drift slightly from the FRR source depending on build):
```
 Virtual Router ID                       2
 Protocol Version                        3
 Autoconfigured                          No
 Shutdown                                No
 Interface                               Vlan100
 VRRP interface (v4)                     Vrrp4-2
 Primary IP (v4)                         1.1.1.1
 Virtual MAC (v4)                        00:00:5e:00:01:02
 Status (v4)                             Master
 Priority                                100
 Effective Priority (v4)                 100
 Preempt Mode                            Yes
 Accept Mode                             Yes
 Checksum with IPv4 Pseudoheader         Yes
 Advertisement Interval                  1000 ms
 Master Advertisement Interval (v4) Rx   1000 ms (stale)
 Advertisements Tx (v4)                  4
 Advertisements Rx (v4)                  0
 Gratuitous ARP Tx (v4)                  1
 State transitions (v4)                  2
 Skew Time (v4)                          600 ms
 Master Down Interval (v4)               3600 ms
 Tracking interface                      0
 IPv4 Addresses                          1
 ..................................      1.1.1.10
```
v6 equivalent uses `VRRP interface (v6)`, `Primary IP (v6)`, `Virtual MAC (v6)` (`00:00:5e:00:02:<vrid-hex>`), `Status (v6)`, `Effective Priority (v6)`, `Neigh. Adverts Tx (v6)` instead of Gratuitous ARP, `IPv6 Addresses`.

Read: `VRRP interface (v4/v6)` = `None` means FRR never attached to the macvlan (broken hop 3). `Priority` vs `Effective Priority` differs once track-interface decrements apply. `Master Advertisement Interval Rx` stays `(stale)` if no adverts were ever received (expected on a lone/Master router).

Kernel layer:
```
ip -d link show Vrrp4-<vrid>     ip -d link show Vrrp6-<vrid>
ip -d addr show Vrrp4-<vrid>     ip -d addr show Vrrp6-<vrid>
```
Example (Master, priority 2):
```
$ ip -d link show Vrrp4-2
83: Vrrp4-2@Vlan100: <BROADCAST,MULTICAST,UP,LOWER_UP> ...
    link/ether 00:00:5e:00:01:02 ... macvlan mode bridge ...
$ ip -d addr show Vrrp4-2
    inet 1.1.1.10/24 scope global noprefixroute Vrrp4-2
```
`state UP` / `LOWER_UP` = this node currently Master (protodown cleared). `state DOWN` = Backup/Init (protodown set). The VIP stays assigned to the macvlan regardless of role — role is expressed via link state, not address presence.

`STATE_DB` snapshot:
```
sonic-db-cli STATE_DB hgetall "VRRP_STATE_TABLE|<ifname>|<vrid>"
sonic-db-cli STATE_DB hgetall "VRRP6_STATE_TABLE|<ifname>|<vrid>"
```
Example:
```
$ sonic-db-cli STATE_DB hgetall "VRRP_STATE_TABLE|Vlan100|2"
{'effective_priority': '100', 'state': 'Master', 'last_changed': '1789457817'}
```
Fields are exactly `effective_priority`, `state` (`Master`/`Backup`/`Init`), `last_changed` (unix epoch of last transition).

`APPL_DB` — what `vrrpsyncd` believes is operationally forwarding, prerequisite for Step 4:
```
sonic-db-cli APPL_DB hgetall "VRRP_TABLE:<ifname>|<vip>/<masklen>"
```
Example:
```
$ sonic-db-cli APPL_DB hgetall "VRRP_TABLE:Vlan100|1.1.1.10/32"
{'vmac': '00:00:5e:00:01:02'}
```
Table name is `VRRP_TABLE` for both v4 and v6; mask is always `/32` for v4 and `/128` for v6 regardless of the VIP's configured subnet mask. Absence of this key when the node should be Master means hop 4 (`vrrpsyncd`) never saw the macvlan come up — check its logs (Step 3) and the kernel link state above.

## Step 3 — Logs

FRR's default log level is `informational` (`log syslog informational`) — `debug vrrp ...` output is `LOG_DEBUG` and won't appear unless you raise the level (`log syslog debugging`) or watch interactively (`vtysh` + `terminal monitor`).

| Component | Container | grep tag |
|---|---|---|
| `frrcfgd` | `bgp` | `[vrrp cfgd](vrrp)`, `[vrrp cfgd](vrrp6)`, `[bgp cfgd](vrrp track)` — shows the exact `vtysh` commands pushed, plus the deferred-field `WARNING` |
| FRR `vrrpd` | `bgp` | `vrrpd` — transitions log as `<if> <family> <vrid>: <OLD> -> <NEW>` |
| `vrrpmgrd` | `swss` | `vrrpmgrd` — `Set vrrp on intf[...] vrid[...]`, `Add vitrual intf[...]`, `Failed to ...` (auto-retries) |
| `vrrpsyncd` | `swss` | `vrrpsyncd` — `RTM_NEWLINK`/`RTM_NEWADDR`/`RTM_DELADDR` on `Vrrp*` interfaces |
| `orchagent` (`VrrpOrch`) | `swss` | `vrrp orch` — `create_router_interface`/route success or `Failed to program Vrrp Mac/IP on interface ..., rv:<sai_status>` |

SONiC forwards container syslog to the host: `grep <tag> /var/log/syslog` on the host works without `docker exec`.

Enable FRR VRRP protocol debugging:
```
docker exec -it bgp vtysh
configure terminal
 debug vrrp protocol
 debug vrrp packets
 debug vrrp sockets
 debug vrrp zebra
 debug vrrp arp        # v4 gratuitous ARP
 debug vrrp ndisc      # v6 neighbor discovery
 debug vrrp autoconfigure
end
show debugging
```
Turn off with `no debug vrrp ...` when done.

## Step 4 — SAI/ASIC layer

Once `APPL_DB` `VRRP_TABLE` has the VIP (Step 2), confirm `orchagent` programmed hardware:
```
sonic-db-cli ASIC_DB keys "ASIC_STATE:SAI_OBJECT_TYPE_ROUTER_INTERFACE:*"
sonic-db-cli ASIC_DB keys "ASIC_STATE:SAI_OBJECT_TYPE_ROUTE_ENTRY:*"
sonic-db-cli ASIC_DB keys "ASIC_STATE:SAI_OBJECT_TYPE_FDB_ENTRY:*"
show mac | grep -i "00:00:5e:00"
```
- Match the route entry's destination to the VIP; its `SAI_ROUTE_ENTRY_ATTR_NEXT_HOP_ID` must point at the router-interface created with the VRRP virtual MAC (`00:00:5e:00:01:<vrid-hex>` v4, `00:00:5e:00:02:<vrid-hex>` v6).
- `orchagent` syslog `rv:0` = success; non-zero `sai_status_t` = ASIC rejected the object (resource exhaustion, or vendor SAI lacks `SAI_ROUTER_INTERFACE_ATTR_IS_VIRTUAL`).
- `VrrpOrch` only flushes the *learned* FDB entry for the vmac it owns — a stale static/other entry can still black-hole traffic; check the FDB dump above.
- Everything programmed but traffic still fails to reach the VIP → generic L2/L3 forwarding issue (port state, LAG hashing, ACLs, peer routing), not VRRP-specific.

## VRRP_TRACK (priority tracking)

`config interface vrrp track_interface add <ifname> <vrid> <track_ifname> <priority_increment>` is pushed by `frrcfgd` as:
```
vrrp <vrid> track-interface <track_ifname> priority-dec <priority_increment>     # v6: vrrp6 ...
```
1. `sonic-db-cli CONFIG_DB hgetall "VRRP_TRACK|<ifname>|<vrid>|<track_ifname>"` — `priority_increment` 10-50, max 8 tracked interfaces per VRRP instance.
2. Grep syslog for `[bgp cfgd](vrrp track)` to confirm `frrcfgd` pushed it.
3. Compare `Priority` vs `Effective Priority (v4/v6)` in `show vrrp`/`show vrrp6` — effective priority should drop by `priority_increment` per currently-down tracked interface.
4. If effective priority never moves when the tracked interface flaps: either the `track-interface` line never reached FRR (step 2), or FRR isn't getting the zebra interface-down event (`debug vrrp zebra`).
5. Field is named `priority_increment` in CONFIG_DB/YANG but FRR's CLI/behavior is `priority-dec` — it decrements priority when the tracked interface is down.

## Quick triage checklist

```
[ ] CONFIG_DB has expected VRRP/VRRP6/VRRP_TRACK rows, vip@ present, subnet matches parent intf
[ ] Parent interface STATE_DB-ready (STATE_VLAN_TABLE / STATE_LAG_TABLE / STATE_PORT_TABLE)
[ ] frrcfgd syslog shows the vtysh commands pushed, no deferred-field warnings for fields you need
[ ] show vrrp/vrrp6: VRRP interface != "None", Status/Effective Priority as expected
[ ] ip -d link show Vrrp4-<vrid>/Vrrp6-<vrid>: link state (UP=Master, DOWN=Backup) matches show vrrp Status
[ ] vrrpsyncd syslog shows RTM_NEWADDR/RTM_NEWLINK for the VIP when this node should be Master
[ ] APPL_DB VRRP_TABLE:<ifname>|<vip>/<mask> has the vmac entry
[ ] orchagent syslog shows create_router_interface/create_route_entry rv:0
[ ] ASIC_DB has the router-interface + route entry, next-hop matches; no stale FDB entry for the vmac
```
