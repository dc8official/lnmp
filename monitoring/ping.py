from __future__ import annotations
import logging
import asyncio
import re
from dataclasses import dataclass
from typing import Optional
from icmplib import async_ping

@dataclass
class PingResult:
    success_count: int
    failed_count: int
    avg_rtt_ms: Optional[float]

    @property
    def health_score(self) -> float:
        total = self.success_count + self.failed_count
        if total == 0:
            return 0.0
        return round((self.success_count / total) * 100.0, 2)

    @property
    def total_count(self) -> int:
        return self.success_count + self.failed_count

async def run_system_ping_fallback(
    ip_address: str,
    count: int,
    interval: float,
    timeout: float,
) -> PingResult:
    """
    Fallback method that spawns the native system 'ping' command as a subprocess.
    This works reliably in standard unprivileged user spaces because the system
    ping binary usually has the SUID capability or raw socket permissions.
    """
    try:
        # non-root users cannot set ping interval < 0.2
        safe_interval = max(0.2, interval)
        
        proc = await asyncio.create_subprocess_exec(
            "ping",
            "-c", str(count),
            "-i", str(safe_interval),
            "-W", str(int(timeout)),
            ip_address,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        stdout_str = stdout.decode("utf-8", errors="ignore")
        
        transmitted = 0
        received = 0
        match_stats = re.search(r"(\d+) packets transmitted,\s+(\d+)\s+(packets\s+)?received", stdout_str)
        if match_stats:
            transmitted = int(match_stats.group(1))
            received = int(match_stats.group(2))
        else:
            tx_match = re.search(r"(\d+)\s+packets transmitted", stdout_str)
            rx_match = re.search(r"(\d+)\s+(packets\s+)?received", stdout_str)
            if tx_match:
                transmitted = int(tx_match.group(1))
            if rx_match:
                received = int(rx_match.group(1))
                
        if transmitted == 0:
            transmitted = count
            
        failed_count = max(0, transmitted - received)
        
        avg_rtt = None
        match_rtt = re.search(r"rtt\s+min/avg/max/mdev\s+=\s+[\d\.]+/(?P<avg>[\d\.]+)/", stdout_str)
        if match_rtt:
            avg_rtt = float(match_rtt.group("avg"))
        else:
            match_rt = re.search(r"round-trip\s+min/avg/max\s+=\s+[\d\.]+/(?P<avg>[\d\.]+)/", stdout_str)
            if match_rt:
                avg_rtt = float(match_rt.group("avg"))
                
        return PingResult(
            success_count=received,
            failed_count=failed_count,
            avg_rtt_ms=avg_rtt,
        )
        
    except Exception as e:
        logging.getLogger(__name__).warning(
            f"System ping fallback failed for {ip_address}: {type(e).__name__}: {e}"
        )
        return PingResult(
            success_count=0,
            failed_count=count,
            avg_rtt_ms=None,
        )

async def run_ping_cycle(
    ip_address: str,
    count: int,
    interval: float,
    timeout: float = 2.0,
    privileged: bool = True,
) -> PingResult:
    try:
        host = await async_ping(
            address=ip_address,
            count=count,
            interval=interval,
            timeout=timeout,
            privileged=privileged,
        )
        success_count = host.packets_received
        failed_count = host.packets_sent - host.packets_received
        avg_rtt_ms = host.avg_rtt if host.packets_received > 0 else None
        
        return PingResult(
            success_count=success_count,
            failed_count=failed_count,
            avg_rtt_ms=avg_rtt_ms,
        )
    except (PermissionError, Exception) as e:
        if privileged:
            logging.getLogger(__name__).info(
                f"Privileged ping failed for {ip_address} ({type(e).__name__}). Retrying with unprivileged socket..."
            )
            try:
                host = await async_ping(
                    address=ip_address,
                    count=count,
                    interval=interval,
                    timeout=timeout,
                    privileged=False,
                )
                success_count = host.packets_received
                failed_count = host.packets_sent - host.packets_received
                avg_rtt_ms = host.avg_rtt if host.packets_received > 0 else None
                
                return PingResult(
                    success_count=success_count,
                    failed_count=failed_count,
                    avg_rtt_ms=avg_rtt_ms,
                )
            except Exception as fallback_err:
                logging.getLogger(__name__).info(
                    f"Unprivileged socket ping also failed for {ip_address} ({type(fallback_err).__name__}). Falling back to system subprocess ping..."
                )
                return await run_system_ping_fallback(
                    ip_address=ip_address,
                    count=count,
                    interval=interval,
                    timeout=timeout,
                )
        else:
            logging.getLogger(__name__).info(
                f"Unprivileged socket ping failed for {ip_address} ({type(e).__name__}). Falling back to system subprocess ping..."
            )
            return await run_system_ping_fallback(
                ip_address=ip_address,
                count=count,
                interval=interval,
                timeout=timeout,
            )

def classify_ping_result(
    result: PingResult,
) -> tuple[str, str]:
    if result.total_count == 0:
        return "DOWN", "DOWN"

    ratio = result.success_count / result.total_count

    if ratio == 1.0:
        return "UP", "UP"
    elif ratio >= 0.6:
        return "UP", "UP-UNSTABLE"
    elif ratio > 0.0:
        return "DOWN", "DOWN-UNSTABLE"
    else:
        return "DOWN", "DOWN"
