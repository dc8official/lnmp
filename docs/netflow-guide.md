# LNMP Network Flow Telemetry Configuration & Operations Guide (v3.2.0)

This operational manual details the architecture, firewall configuration, vendor router setup, and troubleshooting procedures for **Network Flow Telemetry Ingestion (NetFlow v5, NetFlow v9, and IPFIX)** in LNMP v3.2.0.

---

## 1. Architectural Overview

LNMP v3.2.0 introduces real-time, high-volume flow ingestion completely isolated from ICMP polling daemons:

```
+-------------------------------------------------------------------------------+
|                        ROUTER / SWITCH / FIREWALL                             |
|  (Cisco IOS-XE, Juniper Junos, Fortinet, Mikrotik, Linux softflowd)           |
+---------------------------------------+---------------------------------------+
                                        |
                   UDP 2055 (NetFlow v5/v9) / UDP 4739 (IPFIX)
                                        v
+-------------------------------------------------------------------------------+
|                       LNMP COLLECTOR DAEMON (netmon-flowd)                    |
|  - Async Datagram Listeners (4MB SO_RCVBUF)                                   |
|  - Zero-alloc binary parsers (v5, v9 template cache, IPFIX RFC 7011/7012)     |
|  - Fast wire pipeline into Redis 6+ Stream: stream:netflow:raw                 |
+---------------------------------------+---------------------------------------+
                                        |
                                        v
+-------------------------------------------------------------------------------+
|                  CORRELATOR & MICRO-BATCH AGGREGATOR                          |
|  - Dual-role O(1) in-memory lookup table (Exporters & Monitored Participants) |
|  - Port normalizer (collapses ephemeral ports 1024-65535 to preserve index)  |
|  - Unmatched exporter candidate discovery (15-minute TTL in Redis)            |
|  - 1-minute micro-batch accumulator with bulk UPSERT                          |
+---------------------------------------+---------------------------------------+
                                        |
                                        v
+-------------------------------------------------------------------------------+
|                    TIMESCALEDB MULTI-TIER ROLLUPS                             |
|  - flow_minute_rollups (Hypertable: 1-day chunk, 1d compression, 7d retain)  |
|  - flow_hourly_rollups (Continuous Aggregate: 30-day retention)               |
|  - flow_daily_rollups  (Continuous Aggregate: 365-day retention)              |
+-------------------------------------------------------------------------------+
```

---

## 2. Firewall & Port Requirements

Ensure that the LNMP host permits incoming UDP datagrams from your network infrastructure:

| Protocol | Default Port | Usage | Transport |
| :--- | :--- | :--- | :--- |
| **NetFlow v5 / v9** | `UDP 2055` | Cisco, Mikrotik, Linux, Fortinet flow export | UDP |
| **IPFIX** | `UDP 4739` | IANA standard flow export (Juniper, OVS, VyOS) | UDP |

### UFW Configuration (Ubuntu/Debian)

```bash
# Allow NetFlow v5/v9 from internal subnets
sudo ufw allow from 10.0.0.0/8 to any port 2055 proto udp comment 'NetFlow Ingestion'
sudo ufw allow from 172.16.0.0/12 to any port 2055 proto udp comment 'NetFlow Ingestion'
sudo ufw allow from 192.168.0.0/16 to any port 2055 proto udp comment 'NetFlow Ingestion'

# Allow IPFIX from internal subnets
sudo ufw allow from 10.0.0.0/8 to any port 4739 proto udp comment 'IPFIX Ingestion'
sudo ufw allow from 172.16.0.0/12 to any port 4739 proto udp comment 'IPFIX Ingestion'
sudo ufw allow from 192.168.0.0/16 to any port 4739 proto udp comment 'IPFIX Ingestion'
```

---

## 3. Router & Device Configuration Examples

### 3.1 Cisco IOS-XE (Flexible NetFlow - NetFlow v9)

```cisco
! 1. Define Flow Record
flow record LNMP-FLOW-RECORD
 match ipv4 source address
 match ipv4 destination address
 match ipv4 protocol
 match transport source-port
 match transport destination-port
 match interface input
 match interface output
 collect counter bytes long
 collect counter packets long
 collect timestamp sys-uptime first
 collect timestamp sys-uptime last
 collect transport tcp flags
!
! 2. Define Flow Exporter (Point to LNMP host)
flow exporter LNMP-EXPORTER
 destination 192.168.1.10
 source Loopback0
 transport udp 2055
 export-protocol netflow-v9
 template data timeout 60
!
! 3. Define Flow Monitor
flow monitor LNMP-MONITOR
 record LNMP-FLOW-RECORD
 exporter LNMP-EXPORTER
 cache timeout active 60
 cache timeout inactive 15
!
! 4. Apply to WAN/Core Interfaces
interface GigabitEthernet0/0/0
 ip flow monitor LNMP-MONITOR input
 ip flow monitor LNMP-MONITOR output
```

---

### 3.2 Juniper Junos (inline-jflow - IPFIX)

```junos
services {
    flow-monitoring {
        version-ipfix {
            template LNMP-IPFIX-TEMPLATE {
                flow-active-timeout 60;
                flow-inactive-timeout 15;
                template-refresh-rate {
                    packets 1000;
                    seconds 60;
                }
                ipv4-template;
            }
        }
    }
}
forwarding-options {
    sampling {
        instance LNMP-SAMPLING {
            input {
                rate 1;
            }
            family inet {
                output {
                    flow-server 192.168.1.10 {
                        port 4739;
                        version-ipfix {
                            template LNMP-IPFIX-TEMPLATE;
                        }
                    }
                    inline-jflow {
                        source-address 10.255.255.1;
                    }
                }
            }
        }
    }
}
interfaces {
    ge-0/0/0 {
        unit 0 {
            family inet {
                sampling {
                    input;
                    output;
                }
            }
        }
    }
}
```

---

### 3.3 Fortinet FortiOS (NetFlow v9)

```fortios
config system netflow
    set collector-ip 192.168.1.10
    set collector-port 2055
    set source-ip 10.1.1.1
    set active-flow-timeout 1
    set inactive-flow-timeout 15
    set template-tx-timeout 1
end

# Enable NetFlow export on firewall policies
config firewall policy
    edit 1
        set netflow-sampler both
    next
end
```

---

### 3.4 Mikrotik RouterOS v7 (Traffic Flow - NetFlow v9)

```routeros
/ip traffic-flow
set enabled=yes active-flow-timeout=1m inactive-flow-timeout=15s

/ip traffic-flow target
add dst-address=192.168.1.10 port=2055 version=9
```

---

### 3.5 Linux Host / Server (softflowd)

Install `softflowd` to export NetFlow directly from a Linux gateway or hypervisor:

```bash
sudo apt-get install -y softflowd

# Run softflowd listening on eth0, exporting NetFlow v9 to LNMP
sudo softflowd -i eth0 -n 192.168.1.10:2055 -v 9 -m 8192 -t maxlife=60s
```

---

## 4. Enabling Flow Telemetry in LNMP

1. Log in to the LNMP Web Interface as an **Administrator**.
2. Navigate to **System Settings** -> **Tab 2: Performance & Storage Engine**.
3. Under **Network Flow Telemetry Ingestion (v3.2.0)**:
   - Click **Run System Preflight Check** to verify Redis 6+ and stream write functionality.
   - Toggle **Enable Flow Telemetry Ingestion** to **Active**.
   - Ensure the ports (NetFlow: `2055`, IPFIX: `4739`) match your network topology.
   - Click **Save Global Settings**.
4. Start or restart the `netmon-flowd` service on the host:
   ```bash
   sudo systemctl enable --now netmon-flowd
   sudo systemctl status netmon-flowd
   ```

---

## 5. Exporter IP Mapping & Alias Management

When network devices export flows from loopback interfaces, secondary management subnets, or CARP VIPs, LNMP's automatic correlator tracks them as **Unmatched Exporters**:

1. Open the **Bandwidth** fleet dashboard from the top navigation bar.
2. If unmatched exporters are detected, an alert banner appears:
   > `⚠️ Unmatched Flow Exporter Detected: 10.255.255.1 is streaming NetFlow but is not registered to an endpoint.`
3. Click **Map Exporter IP**:
   - Select the corresponding managed device from the dropdown.
   - Click **Bind Exporter IP**.
4. The secondary IP is added to the endpoint's `flow_exporter_ips` array and immediately synchronized to the in-memory correlator via Redis Pub/Sub (`channel:registry_sync`).

---

## 6. Verification & Troubleshooting

### Check Daemon Health
```bash
sudo systemctl status netmon-flowd
sudo journalctl -u netmon-flowd -f --no-tail
```

### Verify Packet Reception
```bash
# Verify NetFlow packets on UDP 2055
sudo tcpdump -ni any udp port 2055 -c 5

# Verify IPFIX packets on UDP 4739
sudo tcpdump -ni any udp port 4739 -c 5
```

### Inspect Redis Wire Buffer
```bash
# Check raw stream queue depth
redis-cli xlen stream:netflow:raw

# Read the last 2 flow packets ingested
redis-cli xrevrange stream:netflow:raw + - count 2
```

### Query Database Rollups
```bash
sudo -u postgres psql -d netmon -c "SELECT bucket, COUNT(*), SUM(bytes) FROM flow_minute_rollups GROUP BY bucket ORDER BY bucket DESC LIMIT 5;"
```
