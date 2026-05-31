from __future__ import annotations
import logging
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
            except Exception as fallback_err:
                logging.getLogger(__name__).warning(
                    f"Ping cycle failed on fallback for {ip_address}: {type(fallback_err).__name__}: {fallback_err}"
                )
                return PingResult(
                    success_count=0,
                    failed_count=count,
                    avg_rtt_ms=None,
                )
        else:
            logging.getLogger(__name__).warning(
                f"Ping cycle failed for {ip_address}: {type(e).__name__}: {e}"
            )
            return PingResult(
                success_count=0,
                failed_count=count,
                avg_rtt_ms=None,
            )

    success_count = host.packets_received
    failed_count = host.packets_sent - host.packets_received
    avg_rtt_ms = host.avg_rtt if host.packets_received > 0 else None
    
    return PingResult(
        success_count=success_count,
        failed_count=failed_count,
        avg_rtt_ms=avg_rtt_ms,
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
