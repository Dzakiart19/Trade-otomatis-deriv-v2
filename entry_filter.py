"""
=============================================================
ENTRY FILTER - Universal High Chance Entry Filter
=============================================================
Module untuk filter entries high probability trades di semua 
trading strategies.

Fitur:
1. Confidence threshold filtering (70% low-risk, 80% high probability)
2. Volatility check - block extreme volatility
3. Trend alignment check - confirm signal aligns with trend
4. Session time filter - good trading hours
5. Entry score calculation (0-100)
6. Statistics tracking

Compatible dengan:
- Terminal Strategy
- DigitPad Strategy
- AMT (Accumulator) Strategy
- Sniper Strategy
- LDP Strategy
- Multi-Indicator Strategy
=============================================================
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, time
import logging
import math

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RiskMode(Enum):
    """Risk mode untuk entry filtering"""
    LOW_RISK = "LOW_RISK"
    HIGH_PROBABILITY = "HIGH_PROBABILITY"
    AGGRESSIVE = "AGGRESSIVE"


class TradingSession(Enum):
    """Trading session berdasarkan waktu UTC"""
    ASIAN = "ASIAN"
    EUROPEAN = "EUROPEAN"
    AMERICAN = "AMERICAN"
    OFF_HOURS = "OFF_HOURS"


class VolatilityLevel(Enum):
    """Level volatility market"""
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    EXTREME = "EXTREME"


class FilterBlockReason(Enum):
    """Alasan entry diblokir"""
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    EXTREME_VOLATILITY = "EXTREME_VOLATILITY"
    TREND_MISALIGNMENT = "TREND_MISALIGNMENT"
    BAD_SESSION = "BAD_SESSION"
    LOW_SCORE = "LOW_SCORE"


@dataclass
class EntryFilterConfig:
    """
    Konfigurasi untuk Entry Filter.
    
    Attributes:
        min_confidence_low_risk: Minimum confidence untuk low-risk mode (default 70%)
        min_confidence_high_prob: Minimum confidence untuk high probability mode (default 80%)
        min_confidence_aggressive: Minimum confidence untuk aggressive mode (default 60%)
        volatility_low: Threshold volatility rendah
        volatility_normal: Threshold volatility normal
        volatility_high: Threshold volatility tinggi
        volatility_extreme: Threshold volatility extreme
        block_extreme_volatility: Block entries saat extreme volatility
        require_trend_alignment: Wajib alignment trend dengan signal direction
        trend_alignment_boost: Boost score saat trend aligned (+10%)
        preferred_sessions: List trading session yang preferred
        session_time_boost: Boost score saat di preferred session (+5%)
        min_entry_score: Minimum score untuk allow entry
        high_score_threshold: Threshold untuk high quality entry
        risk_mode: Risk mode yang digunakan
    """
    min_confidence_low_risk: float = 0.70
    min_confidence_high_prob: float = 0.80
    min_confidence_aggressive: float = 0.60
    
    volatility_low: float = 0.001
    volatility_normal: float = 0.003
    volatility_high: float = 0.005
    volatility_extreme: float = 0.010
    block_extreme_volatility: bool = True
    
    require_trend_alignment: bool = True
    trend_alignment_boost: float = 0.10
    
    preferred_sessions: List[TradingSession] = field(
        default_factory=lambda: [TradingSession.EUROPEAN, TradingSession.AMERICAN]
    )
    session_time_boost: float = 0.05
    
    min_entry_score: int = 60
    high_score_threshold: int = 80
    
    risk_mode: RiskMode = RiskMode.LOW_RISK
    
    def __post_init__(self):
        """Validate configuration values"""
        self.min_confidence_low_risk = max(0.0, min(1.0, self.min_confidence_low_risk))
        self.min_confidence_high_prob = max(0.0, min(1.0, self.min_confidence_high_prob))
        self.min_confidence_aggressive = max(0.0, min(1.0, self.min_confidence_aggressive))
        self.min_entry_score = max(0, min(100, self.min_entry_score))
        self.high_score_threshold = max(0, min(100, self.high_score_threshold))


@dataclass
class EntryScore:
    """
    Hasil kalkulasi entry score.
    
    Attributes:
        score: Total score 0-100
        allowed: Apakah entry diizinkan
        confidence_score: Score komponen confidence (0.0-1.0)
        volatility_score: Score komponen volatility (0.0-1.0)
        trend_score: Score komponen trend alignment (0.0-1.0)
        session_score: Score komponen session time (0.0-1.0)
        reasons: List alasan keputusan
        block_reasons: List alasan diblokir
        volatility_level: Level volatility saat ini
        current_session: Trading session saat ini
        timestamp: Waktu kalkulasi
    """
    score: int
    allowed: bool
    confidence_score: float
    volatility_score: float
    trend_score: float
    session_score: float
    reasons: List[str] = field(default_factory=list)
    block_reasons: List[str] = field(default_factory=list)
    volatility_level: VolatilityLevel = VolatilityLevel.NORMAL
    current_session: TradingSession = TradingSession.OFF_HOURS
    timestamp: datetime = field(default_factory=datetime.now)
    
    def __str__(self):
        status = "✅ ALLOWED" if self.allowed else "❌ BLOCKED"
        return f"{status} | Score: {self.score}/100 | Session: {self.current_session.value}"
    
    def get_summary(self) -> str:
        """Get detailed summary of entry score"""
        lines = [
            f"Entry Score: {self.score}/100",
            f"Status: {'ALLOWED' if self.allowed else 'BLOCKED'}",
            f"Confidence Score: {self.confidence_score:.2f}",
            f"Volatility Score: {self.volatility_score:.2f} ({self.volatility_level.value})",
            f"Trend Score: {self.trend_score:.2f}",
            f"Session Score: {self.session_score:.2f} ({self.current_session.value})",
        ]
        
        if self.reasons:
            lines.append(f"Reasons: {', '.join(self.reasons)}")
        if self.block_reasons:
            lines.append(f"Block Reasons: {', '.join(self.block_reasons)}")
        
        return "\n".join(lines)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "score": self.score,
            "allowed": self.allowed,
            "confidence_score": self.confidence_score,
            "volatility_score": self.volatility_score,
            "trend_score": self.trend_score,
            "session_score": self.session_score,
            "reasons": self.reasons,
            "block_reasons": self.block_reasons,
            "volatility_level": self.volatility_level.value,
            "current_session": self.current_session.value,
            "timestamp": self.timestamp.isoformat(),
        }


class HighChanceEntryFilter:
    """
    Universal Entry Filter untuk high probability trades.
    Bekerja dengan semua trading strategies.
    
    Scoring Weights:
    - Confidence: 40%
    - Volatility: 25%
    - Trend Alignment: 20%
    - Session Time: 15%
    
    Usage:
        filter = HighChanceEntryFilter()
        
        # Quick check
        allowed = filter.should_allow_entry(
            signal_confidence=0.85,
            volatility=0.002,
            trend_direction="UP",
            signal_direction="CALL"
        )
        
        # Full score calculation
        score = filter.calculate_entry_score(analysis_result)
        print(score.score, score.allowed)
        
        # Get statistics
        stats = filter.get_filter_stats()
    """
    
    CONFIDENCE_WEIGHT = 0.40
    VOLATILITY_WEIGHT = 0.25
    TREND_WEIGHT = 0.20
    SESSION_WEIGHT = 0.15
    
    def __init__(self, config: Optional[EntryFilterConfig] = None):
        """
        Inisialisasi High Chance Entry Filter.
        
        Args:
            config: Optional EntryFilterConfig untuk custom settings
        """
        self.config = config or EntryFilterConfig()
        
        self._stats = {
            "total_signals": 0,
            "allowed_entries": 0,
            "blocked_entries": 0,
            "blocked_by_confidence": 0,
            "blocked_by_volatility": 0,
            "blocked_by_trend": 0,
            "blocked_by_session": 0,
            "blocked_by_score": 0,
            "average_score": 0.0,
            "high_score_entries": 0,
        }
        self._score_history: List[int] = []
        self._last_score: Optional[EntryScore] = None
        
        logger.info(f"🎯 High Chance Entry Filter initialized (mode: {self.config.risk_mode.value})")
    
    def should_allow_entry(
        self,
        signal_confidence: float,
        volatility: float,
        trend_direction: str,
        signal_direction: str
    ) -> bool:
        """
        Quick check apakah entry harus diizinkan.
        
        Args:
            signal_confidence: Confidence sinyal (0.0-1.0)
            volatility: Volatility market saat ini
            trend_direction: Arah trend ("UP", "DOWN", "NEUTRAL")
            signal_direction: Arah sinyal ("CALL", "PUT", "BUY", "SELL")
            
        Returns:
            True jika entry diizinkan, False jika tidak
        """
        min_conf = self._get_min_confidence()
        
        if signal_confidence < min_conf:
            self._stats["blocked_by_confidence"] += 1
            return False
        
        vol_level = self._classify_volatility(volatility)
        if vol_level == VolatilityLevel.EXTREME and self.config.block_extreme_volatility:
            self._stats["blocked_by_volatility"] += 1
            return False
        
        if self.config.require_trend_alignment:
            if not self._check_trend_alignment(trend_direction, signal_direction):
                self._stats["blocked_by_trend"] += 1
                return False
        
        return True
    
    def calculate_entry_score(self, analysis_result: Any) -> EntryScore:
        """
        Kalkulasi comprehensive entry score berdasarkan analysis result.
        
        Args:
            analysis_result: Analysis result dari strategy manapun
            (TerminalAnalysisResult, AccumulatorAnalysisResult, 
            DigitPadAnalysisResult, LDPAnalysisResult, AnalysisResult)
            
        Returns:
            EntryScore dengan detailed scoring breakdown
        """
        self._stats["total_signals"] += 1
        
        confidence = self._extract_confidence(analysis_result)
        volatility = self._extract_volatility(analysis_result)
        trend_direction = self._extract_trend_direction(analysis_result)
        signal_direction = self._extract_signal_direction(analysis_result)
        
        confidence_score = self._calculate_confidence_score(confidence)
        volatility_score = self._calculate_volatility_score(volatility)
        trend_score = self._calculate_trend_score(trend_direction, signal_direction)
        session_score = self._calculate_session_score()
        
        vol_level = self._classify_volatility(volatility)
        current_session = self._get_current_session()
        
        total_score = (
            confidence_score * self.CONFIDENCE_WEIGHT +
            volatility_score * self.VOLATILITY_WEIGHT +
            trend_score * self.TREND_WEIGHT +
            session_score * self.SESSION_WEIGHT
        )
        
        final_score = int(min(100, max(0, total_score * 100)))
        
        reasons = []
        block_reasons = []
        
        allowed = True
        min_conf = self._get_min_confidence()
        
        if confidence < min_conf:
            allowed = False
            block_reasons.append(f"Confidence {confidence:.1%} below minimum {min_conf:.1%}")
            self._stats["blocked_by_confidence"] += 1
        else:
            reasons.append(f"Confidence OK: {confidence:.1%}")
        
        if vol_level == VolatilityLevel.EXTREME and self.config.block_extreme_volatility:
            allowed = False
            block_reasons.append(f"Extreme volatility: {volatility:.4f}")
            self._stats["blocked_by_volatility"] += 1
        elif vol_level == VolatilityLevel.HIGH:
            reasons.append(f"High volatility warning: {volatility:.4f}")
        else:
            reasons.append(f"Volatility OK: {vol_level.value}")
        
        if self.config.require_trend_alignment:
            aligned = self._check_trend_alignment(trend_direction, signal_direction)
            if not aligned:
                allowed = False
                block_reasons.append(f"Trend misalignment: {trend_direction} vs {signal_direction}")
                self._stats["blocked_by_trend"] += 1
            else:
                reasons.append(f"Trend aligned: {trend_direction}")
        
        if final_score < self.config.min_entry_score and allowed:
            allowed = False
            block_reasons.append(f"Score {final_score} below minimum {self.config.min_entry_score}")
            self._stats["blocked_by_score"] += 1
        
        if allowed:
            self._stats["allowed_entries"] += 1
            if final_score >= self.config.high_score_threshold:
                self._stats["high_score_entries"] += 1
        else:
            self._stats["blocked_entries"] += 1
        
        self._score_history.append(final_score)
        if len(self._score_history) > 100:
            self._score_history.pop(0)
        self._stats["average_score"] = sum(self._score_history) / len(self._score_history)
        
        entry_score = EntryScore(
            score=final_score,
            allowed=allowed,
            confidence_score=confidence_score,
            volatility_score=volatility_score,
            trend_score=trend_score,
            session_score=session_score,
            reasons=reasons,
            block_reasons=block_reasons,
            volatility_level=vol_level,
            current_session=current_session,
        )
        
        self._last_score = entry_score
        
        return entry_score
    
    def get_filter_stats(self) -> Dict[str, Any]:
        """
        Get statistik entry filter.
        
        Returns:
            Dictionary berisi statistik filter termasuk:
            - total_signals: Total sinyal yang diproses
            - allowed_entries: Jumlah entry yang diizinkan
            - blocked_entries: Jumlah entry yang diblokir
            - blocked_by_*: Breakdown alasan diblokir
            - allow_rate: Persentase entry yang diizinkan
            - block_rate: Persentase entry yang diblokir
            - average_score: Rata-rata score
            - high_score_entries: Jumlah entry dengan score tinggi
        """
        total = self._stats["total_signals"]
        if total > 0:
            allow_rate = (self._stats["allowed_entries"] / total) * 100
            block_rate = (self._stats["blocked_entries"] / total) * 100
        else:
            allow_rate = 0.0
            block_rate = 0.0
        
        return {
            **self._stats,
            "allow_rate": round(allow_rate, 2),
            "block_rate": round(block_rate, 2),
            "current_risk_mode": self.config.risk_mode.value,
            "min_confidence": self._get_min_confidence(),
            "min_entry_score": self.config.min_entry_score,
        }
    
    def reset_stats(self) -> None:
        """Reset statistik filter"""
        self._stats = {
            "total_signals": 0,
            "allowed_entries": 0,
            "blocked_entries": 0,
            "blocked_by_confidence": 0,
            "blocked_by_volatility": 0,
            "blocked_by_trend": 0,
            "blocked_by_session": 0,
            "blocked_by_score": 0,
            "average_score": 0.0,
            "high_score_entries": 0,
        }
        self._score_history.clear()
        self._last_score = None
        logger.info("📊 Entry filter stats reset")
    
    def set_risk_mode(self, mode: RiskMode) -> None:
        """
        Set risk mode untuk filter.
        
        Args:
            mode: RiskMode (LOW_RISK, HIGH_PROBABILITY, AGGRESSIVE)
        """
        self.config.risk_mode = mode
        logger.info(f"🎯 Risk mode changed to: {mode.value}")
    
    def get_last_score(self) -> Optional[EntryScore]:
        """Get last calculated entry score"""
        return self._last_score
    
    def _get_min_confidence(self) -> float:
        """Get minimum confidence berdasarkan risk mode"""
        if self.config.risk_mode == RiskMode.LOW_RISK:
            return self.config.min_confidence_low_risk
        elif self.config.risk_mode == RiskMode.HIGH_PROBABILITY:
            return self.config.min_confidence_high_prob
        else:
            return self.config.min_confidence_aggressive
    
    def _classify_volatility(self, volatility: float) -> VolatilityLevel:
        """Classify volatility level"""
        if not self._is_valid_number(volatility):
            return VolatilityLevel.NORMAL
        
        if volatility >= self.config.volatility_extreme:
            return VolatilityLevel.EXTREME
        elif volatility >= self.config.volatility_high:
            return VolatilityLevel.HIGH
        elif volatility >= self.config.volatility_normal:
            return VolatilityLevel.NORMAL
        else:
            return VolatilityLevel.LOW
    
    def _check_trend_alignment(self, trend_direction: str, signal_direction: str) -> bool:
        """Check apakah signal direction align dengan trend"""
        trend_upper = trend_direction.upper() if trend_direction else "NEUTRAL"
        signal_upper = signal_direction.upper() if signal_direction else "WAIT"
        
        if signal_upper in ["CALL", "BUY"]:
            return trend_upper in ["UP", "BULLISH", "CALL", "NEUTRAL"]
        elif signal_upper in ["PUT", "SELL"]:
            return trend_upper in ["DOWN", "BEARISH", "PUT", "NEUTRAL"]
        
        if trend_upper in ["NEUTRAL", "SIDEWAYS", "FLAT"]:
            return True
        
        return True
    
    def _get_current_session(self) -> TradingSession:
        """Get trading session saat ini berdasarkan waktu UTC"""
        now = datetime.utcnow().time()
        
        asian_start = time(0, 0)
        asian_end = time(8, 0)
        euro_start = time(8, 0)
        euro_end = time(16, 0)
        us_start = time(13, 0)
        us_end = time(21, 0)
        
        if asian_start <= now < asian_end:
            return TradingSession.ASIAN
        elif euro_start <= now < euro_end:
            if us_start <= now < euro_end:
                return TradingSession.AMERICAN
            return TradingSession.EUROPEAN
        elif us_start <= now < us_end:
            return TradingSession.AMERICAN
        
        return TradingSession.OFF_HOURS
    
    def _calculate_confidence_score(self, confidence: float) -> float:
        """Calculate confidence component score (0.0-1.0)"""
        if not self._is_valid_number(confidence):
            return 0.0
        return min(1.0, max(0.0, confidence))
    
    def _calculate_volatility_score(self, volatility: float) -> float:
        """Calculate volatility component score (0.0-1.0)"""
        vol_level = self._classify_volatility(volatility)
        
        if vol_level == VolatilityLevel.LOW:
            return 1.0
        elif vol_level == VolatilityLevel.NORMAL:
            return 0.85
        elif vol_level == VolatilityLevel.HIGH:
            return 0.50
        else:
            return 0.20
    
    def _calculate_trend_score(self, trend_direction: str, signal_direction: str) -> float:
        """Calculate trend alignment component score (0.0-1.0)"""
        aligned = self._check_trend_alignment(trend_direction, signal_direction)
        
        if aligned:
            return min(1.0, 1.0 + self.config.trend_alignment_boost)
        else:
            return 0.30
    
    def _calculate_session_score(self) -> float:
        """Calculate session time component score (0.0-1.0)"""
        current = self._get_current_session()
        
        if current in self.config.preferred_sessions:
            return min(1.0, 1.0 + self.config.session_time_boost)
        elif current == TradingSession.OFF_HOURS:
            return 0.60
        else:
            return 0.80
    
    def _is_valid_number(self, value: Any) -> bool:
        """Check if value is valid finite number"""
        if value is None:
            return False
        try:
            if math.isnan(float(value)) or math.isinf(float(value)):
                return False
            return True
        except (TypeError, ValueError):
            return False
    
    def _extract_confidence(self, analysis_result: Any) -> float:
        """Extract confidence value dari any analysis result type"""
        if analysis_result is None:
            return 0.0
        
        for attr in ["confidence", "probability", "signal_confidence"]:
            if hasattr(analysis_result, attr):
                val = getattr(analysis_result, attr)
                if isinstance(val, (int, float)) and self._is_valid_number(val):
                    return float(val)
        
        if hasattr(analysis_result, "signal") and analysis_result.signal:
            signal = analysis_result.signal
            if hasattr(signal, "confidence"):
                return float(signal.confidence)
        
        if hasattr(analysis_result, "best_signal") and analysis_result.best_signal:
            return float(analysis_result.best_signal.confidence)
        
        if isinstance(analysis_result, dict):
            return float(analysis_result.get("confidence", 0.0))
        
        return 0.0
    
    def _extract_volatility(self, analysis_result: Any) -> float:
        """Extract volatility value dari any analysis result type"""
        if analysis_result is None:
            return 0.0
        
        for attr in ["volatility", "volatility_score", "atr"]:
            if hasattr(analysis_result, attr):
                val = getattr(analysis_result, attr)
                if isinstance(val, (int, float)) and self._is_valid_number(val):
                    return float(val)
        
        if hasattr(analysis_result, "indicators"):
            indicators = analysis_result.indicators
            if hasattr(indicators, "atr"):
                return float(indicators.atr)
        
        if isinstance(analysis_result, dict):
            return float(analysis_result.get("volatility", 0.0))
        
        return 0.0
    
    def _extract_trend_direction(self, analysis_result: Any) -> str:
        """Extract trend direction dari any analysis result type"""
        if analysis_result is None:
            return "NEUTRAL"
        
        for attr in ["trend_direction", "trend", "direction"]:
            if hasattr(analysis_result, attr):
                val = getattr(analysis_result, attr)
                if isinstance(val, str):
                    return val.upper()
                if hasattr(val, "value"):
                    return str(val.value).upper()
        
        if hasattr(analysis_result, "indicators"):
            indicators = analysis_result.indicators
            if hasattr(indicators, "trend_direction"):
                return str(indicators.trend_direction).upper()
        
        if isinstance(analysis_result, dict):
            return str(analysis_result.get("trend_direction", "NEUTRAL")).upper()
        
        return "NEUTRAL"
    
    def _extract_signal_direction(self, analysis_result: Any) -> str:
        """Extract signal direction dari any analysis result type"""
        if analysis_result is None:
            return "WAIT"
        
        if hasattr(analysis_result, "signal") and analysis_result.signal:
            signal = analysis_result.signal
            if hasattr(signal, "direction"):
                direction = signal.direction
                if hasattr(direction, "value"):
                    return str(direction.value).upper()
                return str(direction).upper()
            if hasattr(signal, "value"):
                return str(signal.value).upper()
        
        if hasattr(analysis_result, "best_signal") and analysis_result.best_signal:
            bs = analysis_result.best_signal
            if hasattr(bs, "direction"):
                direction = bs.direction
                if hasattr(direction, "value"):
                    return str(direction.value).upper()
                return str(direction).upper()
            if hasattr(bs, "contract_type"):
                ct = bs.contract_type
                if hasattr(ct, "value"):
                    ct_val = str(ct.value).upper()
                    if "OVER" in ct_val or "EVEN" in ct_val:
                        return "CALL"
                    elif "UNDER" in ct_val or "ODD" in ct_val:
                        return "PUT"
        
        for attr in ["direction", "signal_direction"]:
            if hasattr(analysis_result, attr):
                val = getattr(analysis_result, attr)
                if val:
                    if hasattr(val, "value"):
                        return str(val.value).upper()
                    return str(val).upper()
        
        if isinstance(analysis_result, dict):
            return str(analysis_result.get("direction", "WAIT")).upper()
        
        return "WAIT"


def create_low_risk_filter() -> HighChanceEntryFilter:
    """
    Factory function untuk low-risk entry filter.
    Minimum confidence: 70%
    Requires trend alignment.
    Blocks extreme volatility.
    """
    config = EntryFilterConfig(
        risk_mode=RiskMode.LOW_RISK,
        min_confidence_low_risk=0.70,
        require_trend_alignment=True,
        block_extreme_volatility=True,
        min_entry_score=60,
    )
    return HighChanceEntryFilter(config)


def create_high_probability_filter() -> HighChanceEntryFilter:
    """
    Factory function untuk high probability entry filter.
    Minimum confidence: 80%
    Requires trend alignment.
    Blocks extreme volatility.
    Higher minimum score.
    """
    config = EntryFilterConfig(
        risk_mode=RiskMode.HIGH_PROBABILITY,
        min_confidence_high_prob=0.80,
        require_trend_alignment=True,
        block_extreme_volatility=True,
        min_entry_score=70,
    )
    return HighChanceEntryFilter(config)


def create_aggressive_filter() -> HighChanceEntryFilter:
    """
    Factory function untuk aggressive entry filter.
    Minimum confidence: 60%
    Does not require trend alignment.
    Lower minimum score.
    """
    config = EntryFilterConfig(
        risk_mode=RiskMode.AGGRESSIVE,
        min_confidence_aggressive=0.60,
        require_trend_alignment=False,
        block_extreme_volatility=True,
        min_entry_score=50,
    )
    return HighChanceEntryFilter(config)


def create_sniper_filter() -> HighChanceEntryFilter:
    """
    Factory function untuk sniper-mode entry filter.
    Very high probability focus.
    Minimum confidence: 85%
    Strict trend alignment.
    Higher minimum score.
    """
    config = EntryFilterConfig(
        risk_mode=RiskMode.HIGH_PROBABILITY,
        min_confidence_high_prob=0.85,
        require_trend_alignment=True,
        block_extreme_volatility=True,
        min_entry_score=75,
        high_score_threshold=85,
    )
    return HighChanceEntryFilter(config)
