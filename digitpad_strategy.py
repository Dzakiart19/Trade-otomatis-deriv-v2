"""
=============================================================
DIGITPAD STRATEGY - Advanced Digit Prediction System
=============================================================
Modul ini mengimplementasikan strategi trading berbasis 
prediksi digit dengan frequency analysis (DigitPad).

Referensi: binarybot.live/digitpad

Fitur:
1. Digit Frequency Analysis (0-9)
2. Hot/Cold Digit Detection
3. Even/Odd Prediction
4. Signals Chart dengan Pattern Detection
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


class DigitPadContractType(Enum):
    """Tipe kontrak DigitPad yang didukung"""
    DIGITOVER = "DIGITOVER"
    DIGITUNDER = "DIGITUNDER"
    DIGITMATCH = "DIGITMATCH"
    DIGITDIFF = "DIGITDIFF"
    DIGITEVEN = "DIGITEVEN"
    DIGITODD = "DIGITODD"


class PredictionType(Enum):
    """Tipe prediksi yang dihasilkan"""
    SINGLE_DIGIT = "SINGLE_DIGIT"
    EVEN_ODD = "EVEN_ODD"
    OVER_UNDER = "OVER_UNDER"


@dataclass
class DigitPadSignal:
    """Hasil analisis DigitPad Strategy"""
    contract_type: DigitPadContractType
    prediction: int
    confidence: float
    payout_estimate: float
    reason: str
    prediction_type: PredictionType = PredictionType.SINGLE_DIGIT
    
    def __str__(self):
        return f"{self.contract_type.value} {self.prediction} (conf: {self.confidence:.1%})"


@dataclass
class DigitPadAnalysisResult:
    """Hasil lengkap analisis DigitPad"""
    signals: List[DigitPadSignal]
    best_signal: Optional[DigitPadSignal]
    digit_frequencies: Dict[int, float]
    even_odd_ratio: Tuple[float, float]
    pattern: str
    hot_digits: List[int] = field(default_factory=list)
    cold_digits: List[int] = field(default_factory=list)
    tick_count: int = 0
    current_streak: int = 0
    streak_digit: int = -1


class DigitPadStrategy:
    """
    DigitPad Strategy - Advanced Digit Prediction System
    
    Menganalisis digit terakhir dari harga untuk menghasilkan
    sinyal trading dengan frequency analysis dan hot/cold detection.
    """
    
    MIN_TICKS_REQUIRED = 50
    MAX_TICK_HISTORY = 500
    HOT_THRESHOLD = 0.15
    COLD_THRESHOLD = 0.05
    
    MIN_CONFIDENCE = 0.60
    HIGH_CONFIDENCE = 0.75
    
    STREAK_THRESHOLD = 3
    EVEN_ODD_IMBALANCE_THRESHOLD = 0.25
    
    PAYOUT_OVER_UNDER = 0.95
    PAYOUT_EVEN_ODD = 0.95
    PAYOUT_DIFFERS = 0.10
    PAYOUT_MATCHES = 9.0
    
    def __init__(self):
        """Inisialisasi DigitPad Strategy"""
        self.tick_history: deque = deque(maxlen=self.MAX_TICK_HISTORY)
        self.digit_history: deque = deque(maxlen=self.MAX_TICK_HISTORY)
        self.recent_digits: deque = deque(maxlen=50)
        
        self.digit_counts: Dict[int, int] = {i: 0 for i in range(10)}
        self.total_ticks: int = 0
        
        self.last_digit: int = -1
        self.current_streak: int = 0
        self.streak_digit: int = -1
        
        self.even_count: int = 0
        self.odd_count: int = 0
        
        logger.info("🎲 DigitPad Strategy initialized")
    
    def add_tick(self, price: float) -> Optional[int]:
        """
        Tambahkan tick baru dan update stats.
        
        Args:
            price: Harga tick (misal: 1234.56)
            
        Returns:
            Digit terakhir yang diekstrak
        """
        if not self._is_valid_price(price):
            return None
        
        digit = self._extract_last_digit(price)
        
        self.tick_history.append(price)
        self.digit_history.append(digit)
        self.recent_digits.append(digit)
        self.total_ticks += 1
        
        self.digit_counts[digit] += 1
        
        if digit % 2 == 0:
            self.even_count += 1
        else:
            self.odd_count += 1
        
        self._update_streak(digit)
        
        return digit
    
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
        """Extract digit terakhir dari harga"""
        price_str = f"{price:.2f}"
        digits = price_str.replace(".", "")
        if digits:
            return int(digits[-1])
        return 0
    
    def _update_streak(self, digit: int) -> None:
        """Update streak tracking"""
        if digit == self.last_digit:
            self.current_streak += 1
        else:
            self.current_streak = 1
            self.streak_digit = digit
        
        self.last_digit = digit
    
    def _calculate_digit_frequencies(self) -> Dict[int, float]:
        """
        Hitung frekuensi setiap digit 0-9.
        
        Returns:
            Dictionary {digit: frequency}
        """
        if self.total_ticks == 0:
            return {i: 0.1 for i in range(10)}
        
        return {
            digit: count / self.total_ticks 
            for digit, count in self.digit_counts.items()
        }
    
    def _get_even_odd_ratio(self) -> Tuple[float, float]:
        """
        Hitung rasio even/odd.
        
        Returns:
            (even_ratio, odd_ratio)
        """
        total = self.even_count + self.odd_count
        if total == 0:
            return (0.5, 0.5)
        
        return (
            self.even_count / total,
            self.odd_count / total
        )
    
    def _detect_patterns(self) -> Dict[str, Any]:
        """
        Deteksi pola (hot digits, cold digits, streaks).
        
        Returns:
            Dictionary dengan pattern info
        """
        frequencies = self._calculate_digit_frequencies()
        
        hot_digits = [d for d in range(10) if frequencies[d] >= self.HOT_THRESHOLD]
        cold_digits = [d for d in range(10) if frequencies[d] <= self.COLD_THRESHOLD]
        
        even_ratio, odd_ratio = self._get_even_odd_ratio()
        
        patterns = []
        
        if hot_digits:
            patterns.append(f"HOT:{','.join(map(str, hot_digits))}")
        
        if cold_digits:
            patterns.append(f"COLD:{','.join(map(str, cold_digits))}")
        
        if self.current_streak >= self.STREAK_THRESHOLD:
            patterns.append(f"STREAK:{self.streak_digit}x{self.current_streak}")
        
        if even_ratio >= 0.60:
            patterns.append("EVEN_DOMINANT")
        elif odd_ratio >= 0.60:
            patterns.append("ODD_DOMINANT")
        
        return {
            'hot_digits': hot_digits,
            'cold_digits': cold_digits,
            'even_ratio': even_ratio,
            'odd_ratio': odd_ratio,
            'streak': self.current_streak,
            'streak_digit': self.streak_digit,
            'pattern_string': "|".join(patterns) if patterns else "BALANCED"
        }
    
    def _generate_signals(self) -> List[DigitPadSignal]:
        """
        Generate sinyal berdasarkan analisis.
        
        Returns:
            List of DigitPadSignal
        """
        signals = []
        
        frequencies = self._calculate_digit_frequencies()
        patterns = self._detect_patterns()
        hot_digits = patterns['hot_digits']
        cold_digits = patterns['cold_digits']
        even_ratio = patterns['even_ratio']
        odd_ratio = patterns['odd_ratio']
        
        for cold_digit in cold_digits:
            freq = frequencies[cold_digit]
            confidence = min(0.90 - freq * 5, 0.85)
            
            if confidence >= self.MIN_CONFIDENCE:
                signals.append(DigitPadSignal(
                    contract_type=DigitPadContractType.DIGITDIFF,
                    prediction=cold_digit,
                    confidence=confidence,
                    payout_estimate=self.PAYOUT_DIFFERS,
                    reason=f"Digit {cold_digit} cold ({freq:.1%}), unlikely to appear",
                    prediction_type=PredictionType.SINGLE_DIGIT
                ))
        
        for hot_digit in hot_digits:
            freq = frequencies[hot_digit]
            confidence = min(0.10 + (freq - 0.10) * 2, 0.20)
            
            if freq >= 0.15:
                signals.append(DigitPadSignal(
                    contract_type=DigitPadContractType.DIGITMATCH,
                    prediction=hot_digit,
                    confidence=confidence,
                    payout_estimate=self.PAYOUT_MATCHES,
                    reason=f"Digit {hot_digit} hot ({freq:.1%}), higher match chance",
                    prediction_type=PredictionType.SINGLE_DIGIT
                ))
        
        imbalance = abs(even_ratio - odd_ratio)
        if imbalance >= self.EVEN_ODD_IMBALANCE_THRESHOLD:
            confidence = min(0.55 + imbalance / 2, 0.70)
            
            if confidence >= self.MIN_CONFIDENCE:
                if even_ratio > odd_ratio:
                    signals.append(DigitPadSignal(
                        contract_type=DigitPadContractType.DIGITODD,
                        prediction=1,
                        confidence=confidence,
                        payout_estimate=self.PAYOUT_EVEN_ODD,
                        reason=f"Even dominant ({even_ratio:.1%}), expecting odd reversion",
                        prediction_type=PredictionType.EVEN_ODD
                    ))
                else:
                    signals.append(DigitPadSignal(
                        contract_type=DigitPadContractType.DIGITEVEN,
                        prediction=0,
                        confidence=confidence,
                        payout_estimate=self.PAYOUT_EVEN_ODD,
                        reason=f"Odd dominant ({odd_ratio:.1%}), expecting even reversion",
                        prediction_type=PredictionType.EVEN_ODD
                    ))
        
        if self.current_streak >= self.STREAK_THRESHOLD and len(self.recent_digits) >= 5:
            streak_confidence = min(0.55 + (self.current_streak - self.STREAK_THRESHOLD) * 0.05, 0.70)
            
            if streak_confidence >= self.MIN_CONFIDENCE:
                if self.streak_digit <= 4:
                    signals.append(DigitPadSignal(
                        contract_type=DigitPadContractType.DIGITOVER,
                        prediction=4,
                        confidence=streak_confidence,
                        payout_estimate=self.PAYOUT_OVER_UNDER,
                        reason=f"Streak {self.current_streak}x low digit ({self.streak_digit}), expect high",
                        prediction_type=PredictionType.OVER_UNDER
                    ))
                else:
                    signals.append(DigitPadSignal(
                        contract_type=DigitPadContractType.DIGITUNDER,
                        prediction=5,
                        confidence=streak_confidence,
                        payout_estimate=self.PAYOUT_OVER_UNDER,
                        reason=f"Streak {self.current_streak}x high digit ({self.streak_digit}), expect low",
                        prediction_type=PredictionType.OVER_UNDER
                    ))
        
        low_count = sum(1 for d in list(self.recent_digits)[-20:] if d <= 4)
        high_count = 20 - low_count if len(self.recent_digits) >= 20 else len(self.recent_digits) - low_count
        
        if len(self.recent_digits) >= 20:
            low_ratio = low_count / 20
            high_ratio = high_count / 20
            zone_imbalance = abs(low_ratio - high_ratio)
            
            if zone_imbalance >= 0.30:
                zone_confidence = min(0.55 + zone_imbalance / 2, 0.70)
                
                if zone_confidence >= self.MIN_CONFIDENCE:
                    if low_ratio > high_ratio:
                        signals.append(DigitPadSignal(
                            contract_type=DigitPadContractType.DIGITOVER,
                            prediction=4,
                            confidence=zone_confidence,
                            payout_estimate=self.PAYOUT_OVER_UNDER,
                            reason=f"Low zone dominant ({low_ratio:.1%}), expecting high reversion",
                            prediction_type=PredictionType.OVER_UNDER
                        ))
                    else:
                        signals.append(DigitPadSignal(
                            contract_type=DigitPadContractType.DIGITUNDER,
                            prediction=5,
                            confidence=zone_confidence,
                            payout_estimate=self.PAYOUT_OVER_UNDER,
                            reason=f"High zone dominant ({high_ratio:.1%}), expecting low reversion",
                            prediction_type=PredictionType.OVER_UNDER
                        ))
        
        return signals
    
    def analyze(self) -> Optional[DigitPadAnalysisResult]:
        """
        Perform full DigitPad analysis dan generate signals.
        
        Returns:
            DigitPadAnalysisResult dengan semua signals dan best signal
        """
        if self.total_ticks < self.MIN_TICKS_REQUIRED:
            return None
        
        frequencies = self._calculate_digit_frequencies()
        patterns = self._detect_patterns()
        signals = self._generate_signals()
        
        best_signal = None
        if signals:
            sorted_signals = sorted(
                signals,
                key=lambda s: s.confidence * (1 + s.payout_estimate / 10),
                reverse=True
            )
            
            valid_signals = [s for s in sorted_signals if s.confidence >= self.MIN_CONFIDENCE]
            
            if valid_signals:
                best_signal = valid_signals[0]
        
        even_ratio, odd_ratio = self._get_even_odd_ratio()
        
        return DigitPadAnalysisResult(
            signals=signals,
            best_signal=best_signal,
            digit_frequencies=frequencies,
            even_odd_ratio=(even_ratio, odd_ratio),
            pattern=patterns['pattern_string'],
            hot_digits=patterns['hot_digits'],
            cold_digits=patterns['cold_digits'],
            tick_count=self.total_ticks,
            current_streak=self.current_streak,
            streak_digit=self.streak_digit
        )
    
    def get_signal_for_trading(self) -> Optional[DigitPadSignal]:
        """
        Return best signal untuk trading.
        
        Returns:
            DigitPadSignal jika ada signal valid, None jika tidak
        """
        result = self.analyze()
        if result is None:
            return None
        
        return result.best_signal
    
    def get_digit_heatmap(self) -> Dict[int, float]:
        """Get digit frequency heatmap"""
        return self._calculate_digit_frequencies()
    
    def get_hot_digits(self) -> List[int]:
        """Get list of hot digits"""
        frequencies = self._calculate_digit_frequencies()
        return [d for d in range(10) if frequencies[d] >= self.HOT_THRESHOLD]
    
    def get_cold_digits(self) -> List[int]:
        """Get list of cold digits"""
        frequencies = self._calculate_digit_frequencies()
        return [d for d in range(10) if frequencies[d] <= self.COLD_THRESHOLD]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current strategy statistics"""
        frequencies = self._calculate_digit_frequencies()
        even_ratio, odd_ratio = self._get_even_odd_ratio()
        patterns = self._detect_patterns()
        
        return {
            'tick_count': self.total_ticks,
            'digit_frequencies': frequencies,
            'even_ratio': even_ratio,
            'odd_ratio': odd_ratio,
            'hot_digits': patterns['hot_digits'],
            'cold_digits': patterns['cold_digits'],
            'current_streak': self.current_streak,
            'streak_digit': self.streak_digit,
            'last_digit': self.last_digit,
            'pattern': patterns['pattern_string'],
            'ready': self.total_ticks >= self.MIN_TICKS_REQUIRED
        }
    
    def reset(self) -> None:
        """Reset semua state strategy"""
        self.tick_history.clear()
        self.digit_history.clear()
        self.recent_digits.clear()
        
        self.digit_counts = {i: 0 for i in range(10)}
        self.total_ticks = 0
        
        self.last_digit = -1
        self.current_streak = 0
        self.streak_digit = -1
        
        self.even_count = 0
        self.odd_count = 0
        
        logger.info("🎲 DigitPad Strategy reset")
