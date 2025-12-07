"""
=============================================================
LDP STRATEGY - Last Digit Prediction System
=============================================================
Modul ini mengimplementasikan strategi trading berbasis 
prediksi digit terakhir harga (Last Digit Prediction).

Fitur:
1. Digit Frequency Analysis (Heatmap)
2. Hot/Cold Digit Detection
3. Distribution Analysis (Low 0-4 vs High 5-9)
4. Pattern Recognition untuk prediksi Over/Under/Diff/Match
5. Confidence scoring berbasis statistical analysis

Contract Types Supported:
- OVER/UNDER: Prediksi digit > atau < nilai tertentu
- MATCHES/DIFFERS: Prediksi digit sama atau berbeda dengan target
- EVEN/ODD: Prediksi digit genap atau ganjil

Optimal untuk:
- Modal kecil ($10+)
- Stake minimum $0.35
- Synthetic Indices (R_10, R_25, R_50, R_75, R_100)
=============================================================
"""

from typing import List, Optional, Dict, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from collections import deque
import logging
import math

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LDPContractType(Enum):
    """Tipe kontrak LDP yang didukung"""
    DIGITOVER = "DIGITOVER"
    DIGITUNDER = "DIGITUNDER"
    DIGITMATCH = "DIGITMATCH"
    DIGITDIFF = "DIGITDIFF"
    DIGITEVEN = "DIGITEVEN"
    DIGITODD = "DIGITODD"


class DigitZone(Enum):
    """Zona digit untuk analisis"""
    LOW = "LOW"      # 0-4
    HIGH = "HIGH"    # 5-9
    NEUTRAL = "NEUTRAL"


@dataclass
class DigitStats:
    """Statistik untuk satu digit"""
    digit: int
    count: int = 0
    frequency: float = 0.0
    last_seen: int = 0  # Ticks sejak terakhir muncul
    streak: int = 0     # Berapa kali muncul berturut-turut
    is_hot: bool = False
    is_cold: bool = False


@dataclass
class LDPSignal:
    """Hasil analisis LDP Strategy"""
    contract_type: LDPContractType
    prediction: int  # Nilai prediksi (0-9 untuk digit, threshold untuk over/under)
    confidence: float  # 0.0 - 1.0
    reason: str
    payout_estimate: float  # Estimasi payout percentage
    risk_level: str  # LOW, MEDIUM, HIGH
    
    def __str__(self):
        return f"{self.contract_type.value} {self.prediction} (conf: {self.confidence:.1%})"


@dataclass
class LDPAnalysisResult:
    """Hasil lengkap analisis LDP"""
    signals: List[LDPSignal]
    best_signal: Optional[LDPSignal]
    digit_stats: Dict[int, DigitStats]
    low_zone_percentage: float
    high_zone_percentage: float
    hot_digits: List[int]
    cold_digits: List[int]
    pattern_detected: str
    tick_count: int


class LDPStrategy:
    """
    Last Digit Prediction Strategy
    
    Menganalisis digit terakhir dari harga untuk menghasilkan
    sinyal trading dengan confidence scoring.
    """
    
    # Configuration
    MIN_TICKS_REQUIRED = 50   # Minimum ticks untuk analisis valid
    MAX_TICK_HISTORY = 500    # Maximum tick history yang disimpan
    HOT_THRESHOLD = 0.15      # Digit dengan frequency > 15% = HOT
    COLD_THRESHOLD = 0.05    # Digit dengan frequency < 5% = COLD
    
    # Confidence thresholds
    MIN_CONFIDENCE = 0.55     # Minimum confidence untuk generate signal
    HIGH_CONFIDENCE = 0.70    # High confidence threshold
    
    # Pattern detection
    STREAK_THRESHOLD = 3      # Minimum streak untuk pattern detection
    ZONE_IMBALANCE_THRESHOLD = 0.20  # 20% imbalance untuk zone signal
    
    # Payout estimates (approximate)
    PAYOUT_OVER_UNDER = 0.95  # ~95% payout
    PAYOUT_EVEN_ODD = 0.95    # ~95% payout  
    PAYOUT_DIFFERS = 9.0      # ~900% payout (varies by digit)
    PAYOUT_MATCHES = 9.0      # ~900% payout (varies by digit)
    
    def __init__(self):
        """Inisialisasi LDP Strategy"""
        self.tick_history: deque = deque(maxlen=self.MAX_TICK_HISTORY)
        self.digit_history: deque = deque(maxlen=self.MAX_TICK_HISTORY)
        self.digit_stats: Dict[int, DigitStats] = {i: DigitStats(digit=i) for i in range(10)}
        self.total_ticks: int = 0
        
        # Pattern tracking
        self.last_digit: int = -1
        self.current_streak: int = 0
        self.streak_digit: int = -1
        
        # Zone tracking
        self.low_zone_count: int = 0   # 0-4
        self.high_zone_count: int = 0  # 5-9
        
        # Recent patterns (last 20 digits)
        self.recent_digits: deque = deque(maxlen=20)
        
        logger.info("🎯 LDP Strategy initialized")
    
    def add_tick(self, price: float) -> None:
        """
        Tambahkan tick baru dan update analisis.
        
        Args:
            price: Harga tick (misal: 1234.56)
        """
        if not self._is_valid_price(price):
            return
        
        # Extract last digit
        digit = self._extract_last_digit(price)
        
        self.tick_history.append(price)
        self.digit_history.append(digit)
        self.recent_digits.append(digit)
        self.total_ticks += 1
        
        # Update digit stats
        self._update_digit_stats(digit)
        
        # Update zone tracking
        if digit <= 4:
            self.low_zone_count += 1
        else:
            self.high_zone_count += 1
        
        # Update streak tracking
        self._update_streak(digit)
        
        # Recalculate hot/cold status periodically
        if self.total_ticks % 10 == 0:
            self._recalculate_hot_cold()
    
    def _is_valid_price(self, price: float) -> bool:
        """Validasi harga"""
        if price is None:
            return False
        try:
            if math.isnan(price) or math.isinf(price):
                return False
            if price <= 0:
                return False
            return True
        except (TypeError, ValueError):
            return False
    
    def _extract_last_digit(self, price: float) -> int:
        """
        Extract digit terakhir dari harga.
        
        Untuk Synthetic Indices, digit terakhir adalah digit signifikan
        terakhir sebelum decimal place terakhir.
        
        Examples:
            1234.56 -> 6
            1234.50 -> 0
            123.456 -> 6
        """
        # Convert to string dan ambil digit terakhir yang signifikan
        price_str = f"{price:.2f}"  # Format dengan 2 decimal places
        
        # Hapus decimal point dan ambil digit terakhir
        digits = price_str.replace(".", "")
        
        if digits:
            return int(digits[-1])
        return 0
    
    def _update_digit_stats(self, digit: int) -> None:
        """Update statistik untuk digit"""
        stats = self.digit_stats[digit]
        stats.count += 1
        stats.last_seen = 0
        
        # Update last_seen untuk digit lain
        for d in range(10):
            if d != digit:
                self.digit_stats[d].last_seen += 1
        
        # Recalculate frequencies
        if self.total_ticks > 0:
            for d in range(10):
                self.digit_stats[d].frequency = self.digit_stats[d].count / self.total_ticks
    
    def _update_streak(self, digit: int) -> None:
        """Update streak tracking"""
        if digit == self.last_digit:
            self.current_streak += 1
            self.streak_digit = digit
        else:
            self.current_streak = 1
            self.streak_digit = digit
        
        self.last_digit = digit
        
        # Update streak in stats
        if self.current_streak > self.digit_stats[digit].streak:
            self.digit_stats[digit].streak = self.current_streak
    
    def _recalculate_hot_cold(self) -> None:
        """Recalculate hot/cold status for all digits"""
        if self.total_ticks < self.MIN_TICKS_REQUIRED:
            return
        
        for digit in range(10):
            stats = self.digit_stats[digit]
            stats.is_hot = stats.frequency >= self.HOT_THRESHOLD
            stats.is_cold = stats.frequency <= self.COLD_THRESHOLD
    
    def get_digit_heatmap(self) -> Dict[int, float]:
        """
        Get digit frequency heatmap.
        
        Returns:
            Dictionary {digit: frequency}
        """
        return {d: self.digit_stats[d].frequency for d in range(10)}
    
    def get_hot_digits(self) -> List[int]:
        """Get list of hot digits (appearing frequently)"""
        return [d for d in range(10) if self.digit_stats[d].is_hot]
    
    def get_cold_digits(self) -> List[int]:
        """Get list of cold digits (appearing rarely)"""
        return [d for d in range(10) if self.digit_stats[d].is_cold]
    
    def get_zone_distribution(self) -> Tuple[float, float]:
        """
        Get distribution between low (0-4) and high (5-9) zones.
        
        Returns:
            (low_percentage, high_percentage)
        """
        total = self.low_zone_count + self.high_zone_count
        if total == 0:
            return (0.5, 0.5)
        
        return (
            self.low_zone_count / total,
            self.high_zone_count / total
        )
    
    def analyze(self) -> Optional[LDPAnalysisResult]:
        """
        Perform full LDP analysis dan generate signals.
        
        Returns:
            LDPAnalysisResult dengan semua signals dan best signal
        """
        if self.total_ticks < self.MIN_TICKS_REQUIRED:
            return None
        
        signals: List[LDPSignal] = []
        
        # 1. Analyze Over/Under opportunities
        over_under_signals = self._analyze_over_under()
        signals.extend(over_under_signals)
        
        # 2. Analyze Matches/Differs opportunities
        match_diff_signals = self._analyze_matches_differs()
        signals.extend(match_diff_signals)
        
        # 3. Analyze Even/Odd opportunities
        even_odd_signals = self._analyze_even_odd()
        signals.extend(even_odd_signals)
        
        # Get zone distribution
        low_pct, high_pct = self.get_zone_distribution()
        
        # Detect patterns
        pattern = self._detect_pattern()
        
        # Find best signal (highest confidence with reasonable payout)
        best_signal = None
        if signals:
            # Sort by confidence * payout_estimate
            sorted_signals = sorted(
                signals, 
                key=lambda s: s.confidence * (1 + s.payout_estimate / 10),
                reverse=True
            )
            
            # Filter by minimum confidence
            valid_signals = [s for s in sorted_signals if s.confidence >= self.MIN_CONFIDENCE]
            
            if valid_signals:
                best_signal = valid_signals[0]
        
        return LDPAnalysisResult(
            signals=signals,
            best_signal=best_signal,
            digit_stats=self.digit_stats.copy(),
            low_zone_percentage=low_pct,
            high_zone_percentage=high_pct,
            hot_digits=self.get_hot_digits(),
            cold_digits=self.get_cold_digits(),
            pattern_detected=pattern,
            tick_count=self.total_ticks
        )
    
    def _analyze_over_under(self) -> List[LDPSignal]:
        """
        Analyze Over/Under opportunities.
        
        DIGITOVER: Digit terakhir > prediksi
        DIGITUNDER: Digit terakhir < prediksi
        """
        signals = []
        low_pct, high_pct = self.get_zone_distribution()
        
        # Check for zone imbalance
        imbalance = abs(low_pct - high_pct)
        
        if imbalance >= self.ZONE_IMBALANCE_THRESHOLD:
            if low_pct > high_pct:
                # Low zone dominant -> expect reversion to high (OVER signal)
                confidence = min(0.50 + imbalance, 0.75)
                
                # Find best threshold (4 is common cutoff)
                best_threshold = 4
                
                signals.append(LDPSignal(
                    contract_type=LDPContractType.DIGITOVER,
                    prediction=best_threshold,
                    confidence=confidence,
                    reason=f"Low zone dominant ({low_pct:.1%}), expecting reversion to high",
                    payout_estimate=self.PAYOUT_OVER_UNDER,
                    risk_level="MEDIUM" if confidence >= 0.60 else "HIGH"
                ))
            else:
                # High zone dominant -> expect reversion to low (UNDER signal)
                confidence = min(0.50 + imbalance, 0.75)
                
                # Find best threshold
                best_threshold = 5
                
                signals.append(LDPSignal(
                    contract_type=LDPContractType.DIGITUNDER,
                    prediction=best_threshold,
                    confidence=confidence,
                    reason=f"High zone dominant ({high_pct:.1%}), expecting reversion to low",
                    payout_estimate=self.PAYOUT_OVER_UNDER,
                    risk_level="MEDIUM" if confidence >= 0.60 else "HIGH"
                ))
        
        # Check for streak-based over/under
        if self.current_streak >= self.STREAK_THRESHOLD:
            current_digit = self.last_digit
            
            if current_digit <= 4:
                # Streak of low digits -> consider OVER
                confidence = min(0.55 + (self.current_streak - self.STREAK_THRESHOLD) * 0.05, 0.70)
                signals.append(LDPSignal(
                    contract_type=LDPContractType.DIGITOVER,
                    prediction=4,
                    confidence=confidence,
                    reason=f"Streak of {self.current_streak}x low digit ({current_digit}), expecting reversion",
                    payout_estimate=self.PAYOUT_OVER_UNDER,
                    risk_level="MEDIUM"
                ))
            elif current_digit >= 5:
                # Streak of high digits -> consider UNDER
                confidence = min(0.55 + (self.current_streak - self.STREAK_THRESHOLD) * 0.05, 0.70)
                signals.append(LDPSignal(
                    contract_type=LDPContractType.DIGITUNDER,
                    prediction=5,
                    confidence=confidence,
                    reason=f"Streak of {self.current_streak}x high digit ({current_digit}), expecting reversion",
                    payout_estimate=self.PAYOUT_OVER_UNDER,
                    risk_level="MEDIUM"
                ))
        
        return signals
    
    def _analyze_matches_differs(self) -> List[LDPSignal]:
        """
        Analyze Matches/Differs opportunities.
        
        DIGITMATCH: Digit terakhir = prediksi (high payout ~900%)
        DIGITDIFF: Digit terakhir != prediksi (low payout but safer)
        """
        signals = []
        
        # Find hottest digit for MATCHES
        hot_digits = self.get_hot_digits()
        cold_digits = self.get_cold_digits()
        
        # DIFFERS: Bet that cold digit will NOT appear
        # This is safer because cold digits rarely appear
        if cold_digits:
            coldest_digit = min(cold_digits, key=lambda d: self.digit_stats[d].frequency)
            coldest_freq = self.digit_stats[coldest_digit].frequency
            
            # Calculate confidence based on how cold the digit is
            # Lower frequency = higher confidence it won't appear
            confidence = min(0.90 - coldest_freq * 5, 0.85)  # Max 85%
            
            if confidence >= self.MIN_CONFIDENCE:
                signals.append(LDPSignal(
                    contract_type=LDPContractType.DIGITDIFF,
                    prediction=coldest_digit,
                    confidence=confidence,
                    reason=f"Digit {coldest_digit} is cold ({coldest_freq:.1%}), likely to differ",
                    payout_estimate=0.10,  # ~10% payout for differs
                    risk_level="LOW"
                ))
        
        # MATCHES: Bet that hot digit will appear
        # High risk, high reward strategy
        if hot_digits:
            hottest_digit = max(hot_digits, key=lambda d: self.digit_stats[d].frequency)
            hottest_freq = self.digit_stats[hottest_digit].frequency
            
            # Confidence for matches is lower (10% base chance)
            # Boost based on how hot the digit is
            base_chance = 0.10  # 10% base
            confidence = min(base_chance + (hottest_freq - 0.10) * 2, 0.20)  # Max 20%
            
            if hottest_freq >= 0.12:  # Only if significantly hot
                signals.append(LDPSignal(
                    contract_type=LDPContractType.DIGITMATCH,
                    prediction=hottest_digit,
                    confidence=confidence,
                    reason=f"Digit {hottest_digit} is hot ({hottest_freq:.1%}), consider match",
                    payout_estimate=self.PAYOUT_MATCHES,
                    risk_level="HIGH"
                ))
        
        # Check for "due" digit (long time since appearance)
        max_last_seen = max(self.digit_stats[d].last_seen for d in range(10))
        if max_last_seen >= 30:  # If a digit hasn't appeared in 30+ ticks
            due_digit = max(range(10), key=lambda d: self.digit_stats[d].last_seen)
            
            # "Due" reasoning (gambler's fallacy but can work for short term)
            confidence = min(0.12 + (max_last_seen - 30) * 0.002, 0.18)
            
            signals.append(LDPSignal(
                contract_type=LDPContractType.DIGITMATCH,
                prediction=due_digit,
                confidence=confidence,
                reason=f"Digit {due_digit} hasn't appeared in {max_last_seen} ticks (due)",
                payout_estimate=self.PAYOUT_MATCHES,
                risk_level="HIGH"
            ))
        
        return signals
    
    def _analyze_even_odd(self) -> List[LDPSignal]:
        """
        Analyze Even/Odd opportunities.
        
        Even digits: 0, 2, 4, 6, 8
        Odd digits: 1, 3, 5, 7, 9
        """
        signals = []
        
        if not self.recent_digits or len(self.recent_digits) < 10:
            return signals
        
        # Count even/odd in recent history
        recent_list = list(self.recent_digits)
        even_count = sum(1 for d in recent_list if d % 2 == 0)
        odd_count = len(recent_list) - even_count
        
        total = len(recent_list)
        even_pct = even_count / total
        odd_pct = odd_count / total
        
        # Check for significant imbalance
        imbalance = abs(even_pct - odd_pct)
        
        if imbalance >= 0.25:  # 25% imbalance
            if even_pct > odd_pct:
                # Even dominant -> expect odd
                confidence = min(0.52 + imbalance / 2, 0.65)
                signals.append(LDPSignal(
                    contract_type=LDPContractType.DIGITODD,
                    prediction=1,  # Generic odd
                    confidence=confidence,
                    reason=f"Even dominant ({even_pct:.1%}), expecting odd reversion",
                    payout_estimate=self.PAYOUT_EVEN_ODD,
                    risk_level="MEDIUM"
                ))
            else:
                # Odd dominant -> expect even
                confidence = min(0.52 + imbalance / 2, 0.65)
                signals.append(LDPSignal(
                    contract_type=LDPContractType.DIGITEVEN,
                    prediction=0,  # Generic even
                    confidence=confidence,
                    reason=f"Odd dominant ({odd_pct:.1%}), expecting even reversion",
                    payout_estimate=self.PAYOUT_EVEN_ODD,
                    risk_level="MEDIUM"
                ))
        
        # Check for even/odd streak
        if len(recent_list) >= 5:
            last_5 = recent_list[-5:]
            even_streak = all(d % 2 == 0 for d in last_5)
            odd_streak = all(d % 2 == 1 for d in last_5)
            
            if even_streak:
                signals.append(LDPSignal(
                    contract_type=LDPContractType.DIGITODD,
                    prediction=1,
                    confidence=0.60,
                    reason="5+ even digit streak, expecting odd",
                    payout_estimate=self.PAYOUT_EVEN_ODD,
                    risk_level="MEDIUM"
                ))
            elif odd_streak:
                signals.append(LDPSignal(
                    contract_type=LDPContractType.DIGITEVEN,
                    prediction=0,
                    confidence=0.60,
                    reason="5+ odd digit streak, expecting even",
                    payout_estimate=self.PAYOUT_EVEN_ODD,
                    risk_level="MEDIUM"
                ))
        
        return signals
    
    def _detect_pattern(self) -> str:
        """
        Detect current market pattern.
        
        Returns:
            Pattern description string
        """
        if self.total_ticks < self.MIN_TICKS_REQUIRED:
            return "INSUFFICIENT_DATA"
        
        low_pct, high_pct = self.get_zone_distribution()
        hot_count = len(self.get_hot_digits())
        cold_count = len(self.get_cold_digits())
        
        patterns = []
        
        # Zone dominance
        if low_pct > 0.60:
            patterns.append("LOW_DOMINANT")
        elif high_pct > 0.60:
            patterns.append("HIGH_DOMINANT")
        
        # Digit concentration
        if hot_count >= 3:
            patterns.append("CONCENTRATED")
        elif cold_count >= 3:
            patterns.append("DISTRIBUTED")
        
        # Streak pattern
        if self.current_streak >= 4:
            patterns.append(f"STREAK_{self.streak_digit}")
        
        # Even/Odd imbalance
        recent_list = list(self.recent_digits) if self.recent_digits else []
        if len(recent_list) >= 10:
            even_count = sum(1 for d in recent_list if d % 2 == 0)
            if even_count >= 7:
                patterns.append("EVEN_DOMINANT")
            elif even_count <= 3:
                patterns.append("ODD_DOMINANT")
        
        if patterns:
            return "|".join(patterns)
        return "BALANCED"
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current strategy statistics"""
        low_pct, high_pct = self.get_zone_distribution()
        
        return {
            'tick_count': self.total_ticks,
            'low_zone_pct': low_pct,
            'high_zone_pct': high_pct,
            'hot_digits': self.get_hot_digits(),
            'cold_digits': self.get_cold_digits(),
            'current_streak': self.current_streak,
            'streak_digit': self.streak_digit,
            'last_digit': self.last_digit,
            'pattern': self._detect_pattern(),
            'ready': self.total_ticks >= self.MIN_TICKS_REQUIRED
        }
    
    def get_digit_summary(self) -> str:
        """Get human-readable digit summary"""
        if self.total_ticks < 10:
            return "Insufficient data"
        
        low_pct, high_pct = self.get_zone_distribution()
        hot = self.get_hot_digits()
        cold = self.get_cold_digits()
        
        lines = [
            f"📊 LDP Analysis ({self.total_ticks} ticks)",
            f"Low (0-4): {low_pct:.1%} | High (5-9): {high_pct:.1%}",
            f"🔥 Hot: {hot if hot else 'None'}",
            f"❄️ Cold: {cold if cold else 'None'}",
            f"Pattern: {self._detect_pattern()}"
        ]
        
        if self.current_streak >= 3:
            lines.append(f"⚡ Streak: {self.current_streak}x digit {self.streak_digit}")
        
        return "\n".join(lines)
    
    def clear_history(self) -> None:
        """Reset semua history dan statistik"""
        self.tick_history.clear()
        self.digit_history.clear()
        self.recent_digits.clear()
        self.digit_stats = {i: DigitStats(digit=i) for i in range(10)}
        self.total_ticks = 0
        self.low_zone_count = 0
        self.high_zone_count = 0
        self.last_digit = -1
        self.current_streak = 0
        self.streak_digit = -1
        
        logger.info("🔄 LDP Strategy history cleared")
    
    def get_best_signal_for_small_capital(self) -> Optional[LDPSignal]:
        """
        Get best signal optimized for small capital ($10).
        
        Prioritizes:
        1. High confidence signals
        2. Low risk strategies (DIFFERS, OVER/UNDER, EVEN/ODD)
        3. Avoids high-risk MATCHES unless very confident
        """
        result = self.analyze()
        if not result or not result.signals:
            return None
        
        # Filter out high-risk MATCHES for small capital
        safe_signals = [
            s for s in result.signals 
            if s.contract_type not in [LDPContractType.DIGITMATCH]
            and s.confidence >= self.MIN_CONFIDENCE
        ]
        
        if not safe_signals:
            return None
        
        # Sort by confidence
        safe_signals.sort(key=lambda s: s.confidence, reverse=True)
        
        return safe_signals[0]
