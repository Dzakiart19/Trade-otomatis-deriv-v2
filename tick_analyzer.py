"""
=============================================================
TICK TREND ANALYZER - Advanced Tick Pattern Detection
=============================================================
Modul ini mengimplementasikan analisis tick yang lebih akurat
dengan berbagai teknik pattern detection.

Fitur:
1. Consecutive tick detection (up/down streaks)
2. Momentum calculation dengan multiple windows
3. Pattern recognition (reversal, continuation, etc.)
4. Volatility measurement
5. Support/Resistance level detection
6. Signal generation dengan confidence scoring

Terinspirasi dari:
- binarybot.live/tick-picker
- terminal.nextrader.live
=============================================================
"""

from typing import List, Optional, Dict, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
from datetime import datetime
import logging
import math

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TickDirection(Enum):
    """Arah tick"""
    UP = "UP"
    DOWN = "DOWN"
    NEUTRAL = "NEUTRAL"


class TrendStrength(Enum):
    """Kekuatan trend"""
    STRONG = "STRONG"
    MODERATE = "MODERATE"
    WEAK = "WEAK"
    NONE = "NONE"


class PatternType(Enum):
    """Tipe pattern yang terdeteksi"""
    UPTREND = "UPTREND"
    DOWNTREND = "DOWNTREND"
    REVERSAL_UP = "REVERSAL_UP"
    REVERSAL_DOWN = "REVERSAL_DOWN"
    CONSOLIDATION = "CONSOLIDATION"
    BREAKOUT_UP = "BREAKOUT_UP"
    BREAKOUT_DOWN = "BREAKOUT_DOWN"
    NO_PATTERN = "NO_PATTERN"


@dataclass
class TickSignal:
    """Signal hasil analisis tick"""
    direction: TickDirection
    strength: TrendStrength
    confidence: float
    pattern: PatternType
    reason: str
    entry_price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


@dataclass
class MomentumData:
    """Data momentum calculation"""
    short_momentum: float  # 5 tick momentum
    medium_momentum: float  # 10 tick momentum
    long_momentum: float   # 20 tick momentum
    acceleration: float    # Rate of change
    is_accelerating: bool
    is_decelerating: bool


@dataclass
class VolatilityData:
    """Data volatilitas"""
    current_volatility: float
    average_volatility: float
    volatility_percentile: float  # 0-100
    is_high_volatility: bool
    is_low_volatility: bool


class TickTrendAnalyzer:
    """
    Advanced Tick Trend Analyzer
    
    Menganalisis pergerakan tick untuk menghasilkan sinyal trading
    dengan confidence scoring yang akurat.
    """
    
    # Configuration
    MIN_TICKS_REQUIRED = 30
    MAX_TICK_HISTORY = 500
    
    # Streak thresholds
    MIN_STREAK_FOR_SIGNAL = 3
    STRONG_STREAK_THRESHOLD = 5
    
    # Momentum windows
    SHORT_WINDOW = 5
    MEDIUM_WINDOW = 10
    LONG_WINDOW = 20
    
    # Volatility settings
    VOLATILITY_WINDOW = 20
    HIGH_VOLATILITY_PERCENTILE = 75
    LOW_VOLATILITY_PERCENTILE = 25
    
    # Confidence thresholds
    MIN_CONFIDENCE = 0.55
    HIGH_CONFIDENCE = 0.70
    
    # Pattern detection
    REVERSAL_STREAK_MIN = 4  # Min streak sebelum reversal signal
    CONSOLIDATION_THRESHOLD = 0.001  # Max price change untuk consolidation
    
    def __init__(self):
        """Initialize Tick Trend Analyzer"""
        self.tick_history: deque = deque(maxlen=self.MAX_TICK_HISTORY)
        self.direction_history: deque = deque(maxlen=self.MAX_TICK_HISTORY)
        self.volatility_history: deque = deque(maxlen=100)
        
        self.total_ticks: int = 0
        self.last_price: float = 0.0
        
        # Streak tracking
        self.current_streak: int = 0
        self.streak_direction: TickDirection = TickDirection.NEUTRAL
        self.max_up_streak: int = 0
        self.max_down_streak: int = 0
        
        # Momentum tracking
        self.momentum_data: Optional[MomentumData] = None
        
        # Support/Resistance
        self.support_levels: List[float] = []
        self.resistance_levels: List[float] = []
        
        # Statistics
        self.up_ticks: int = 0
        self.down_ticks: int = 0
        
        logger.info("📈 Tick Trend Analyzer initialized")
    
    def add_tick(self, price: float) -> Optional[TickDirection]:
        """
        Add new tick dan update analysis.
        
        Args:
            price: Harga tick baru
            
        Returns:
            Direction of tick movement
        """
        if not self._is_valid_price(price):
            return None
        
        self.tick_history.append(price)
        self.total_ticks += 1
        
        # Calculate direction
        direction = self._calculate_direction(price)
        self.direction_history.append(direction)
        
        # Update stats
        if direction == TickDirection.UP:
            self.up_ticks += 1
        elif direction == TickDirection.DOWN:
            self.down_ticks += 1
        
        # Update streak
        self._update_streak(direction)
        
        # Update volatility
        self._update_volatility(price)
        
        # Update momentum
        if self.total_ticks >= self.SHORT_WINDOW:
            self._update_momentum()
        
        # Update support/resistance periodically
        if self.total_ticks % 50 == 0:
            self._update_support_resistance()
        
        self.last_price = price
        
        return direction
    
    def _is_valid_price(self, price: float) -> bool:
        """Validate price"""
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
    
    def _calculate_direction(self, price: float) -> TickDirection:
        """Calculate tick direction"""
        if self.last_price == 0.0:
            return TickDirection.NEUTRAL
        
        diff = price - self.last_price
        
        if diff > 0:
            return TickDirection.UP
        elif diff < 0:
            return TickDirection.DOWN
        else:
            return TickDirection.NEUTRAL
    
    def _update_streak(self, direction: TickDirection) -> None:
        """Update streak tracking"""
        if direction == TickDirection.NEUTRAL:
            return
        
        if direction == self.streak_direction:
            self.current_streak += 1
        else:
            # Streak broken
            if self.streak_direction == TickDirection.UP:
                if self.current_streak > self.max_up_streak:
                    self.max_up_streak = self.current_streak
            elif self.streak_direction == TickDirection.DOWN:
                if self.current_streak > self.max_down_streak:
                    self.max_down_streak = self.current_streak
            
            self.streak_direction = direction
            self.current_streak = 1
    
    def _update_volatility(self, price: float) -> None:
        """Update volatility calculation"""
        if self.last_price > 0:
            change = abs(price - self.last_price)
            pct_change = change / self.last_price
            self.volatility_history.append(pct_change)
    
    def _update_momentum(self) -> None:
        """Update momentum calculations"""
        prices = list(self.tick_history)
        
        if len(prices) < self.LONG_WINDOW:
            return
        
        # Calculate momentum for different windows
        short_momentum = self._calculate_momentum(prices[-self.SHORT_WINDOW:])
        medium_momentum = self._calculate_momentum(prices[-self.MEDIUM_WINDOW:])
        long_momentum = self._calculate_momentum(prices[-self.LONG_WINDOW:])
        
        # Calculate acceleration (momentum of momentum)
        if len(prices) >= self.MEDIUM_WINDOW + 5:
            prev_momentum = self._calculate_momentum(prices[-(self.MEDIUM_WINDOW + 5):-5])
            acceleration = medium_momentum - prev_momentum
        else:
            acceleration = 0.0
        
        self.momentum_data = MomentumData(
            short_momentum=short_momentum,
            medium_momentum=medium_momentum,
            long_momentum=long_momentum,
            acceleration=acceleration,
            is_accelerating=acceleration > 0 and medium_momentum > 0,
            is_decelerating=acceleration < 0 or (acceleration > 0 and medium_momentum < 0)
        )
    
    def _calculate_momentum(self, prices: List[float]) -> float:
        """Calculate momentum sebagai rate of change"""
        if len(prices) < 2:
            return 0.0
        
        first_price = prices[0]
        last_price = prices[-1]
        
        if first_price == 0:
            return 0.0
        
        return (last_price - first_price) / first_price * 100
    
    def _update_support_resistance(self) -> None:
        """Update support and resistance levels"""
        if len(self.tick_history) < 50:
            return
        
        prices = list(self.tick_history)[-100:]
        
        # Simple pivot point calculation
        highest = max(prices)
        lowest = min(prices)
        
        # Find local minima (support) and maxima (resistance)
        self.support_levels = [lowest]
        self.resistance_levels = [highest]
        
        # Add intermediate levels
        mid = (highest + lowest) / 2
        self.support_levels.append(mid - (mid - lowest) / 2)
        self.resistance_levels.append(mid + (highest - mid) / 2)
    
    def get_volatility_data(self) -> Optional[VolatilityData]:
        """Get current volatility data"""
        if len(self.volatility_history) < 10:
            return None
        
        vol_list = list(self.volatility_history)
        current = vol_list[-1] if vol_list else 0
        average = sum(vol_list) / len(vol_list)
        
        # Calculate percentile
        sorted_vol = sorted(vol_list)
        position = sorted_vol.index(current) if current in sorted_vol else len(sorted_vol) // 2
        percentile = (position / len(sorted_vol)) * 100
        
        return VolatilityData(
            current_volatility=current,
            average_volatility=average,
            volatility_percentile=percentile,
            is_high_volatility=percentile >= self.HIGH_VOLATILITY_PERCENTILE,
            is_low_volatility=percentile <= self.LOW_VOLATILITY_PERCENTILE
        )
    
    def analyze(self) -> Optional[TickSignal]:
        """
        Perform full analysis dan generate signal.
        
        Returns:
            TickSignal jika ada signal yang valid, None jika tidak
        """
        if self.total_ticks < self.MIN_TICKS_REQUIRED:
            return None
        
        if len(self.tick_history) < 2:
            return None
        
        current_price = self.tick_history[-1]
        
        # Detect pattern
        pattern = self._detect_pattern()
        
        # Calculate base confidence
        base_confidence = 0.50
        
        # Analyze streak
        streak_signal = self._analyze_streak()
        if streak_signal:
            return streak_signal
        
        # Analyze momentum
        momentum_signal = self._analyze_momentum(current_price)
        if momentum_signal:
            return momentum_signal
        
        # Analyze pattern-based signals
        pattern_signal = self._analyze_pattern(pattern, current_price)
        if pattern_signal:
            return pattern_signal
        
        return None
    
    def _detect_pattern(self) -> PatternType:
        """Detect current market pattern"""
        if self.total_ticks < self.MIN_TICKS_REQUIRED:
            return PatternType.NO_PATTERN
        
        prices = list(self.tick_history)[-20:]
        
        if len(prices) < 10:
            return PatternType.NO_PATTERN
        
        # Calculate trend
        first_half_avg = sum(prices[:10]) / 10
        second_half_avg = sum(prices[10:]) / len(prices[10:])
        
        change_pct = (second_half_avg - first_half_avg) / first_half_avg if first_half_avg > 0 else 0
        
        # Check for consolidation
        price_range = max(prices) - min(prices)
        avg_price = sum(prices) / len(prices)
        range_pct = price_range / avg_price if avg_price > 0 else 0
        
        if range_pct < self.CONSOLIDATION_THRESHOLD:
            return PatternType.CONSOLIDATION
        
        # Check for reversal
        if self.current_streak >= self.REVERSAL_STREAK_MIN:
            if self.streak_direction == TickDirection.UP:
                # Long uptrend, might reverse down
                if self.momentum_data and self.momentum_data.is_decelerating:
                    return PatternType.REVERSAL_DOWN
            elif self.streak_direction == TickDirection.DOWN:
                # Long downtrend, might reverse up
                if self.momentum_data and self.momentum_data.is_decelerating:
                    return PatternType.REVERSAL_UP
        
        # Simple trend detection
        if change_pct > 0.001:
            return PatternType.UPTREND
        elif change_pct < -0.001:
            return PatternType.DOWNTREND
        
        return PatternType.NO_PATTERN
    
    def _analyze_streak(self) -> Optional[TickSignal]:
        """Analyze streak untuk signal generation"""
        if self.current_streak < self.MIN_STREAK_FOR_SIGNAL:
            return None
        
        current_price = self.tick_history[-1]
        
        # Calculate confidence based on streak length
        streak_factor = min(self.current_streak / 10, 1.0)
        
        # Reversal expectation after long streak
        if self.current_streak >= self.STRONG_STREAK_THRESHOLD:
            # Strong streak - expect reversal
            confidence = 0.55 + (streak_factor * 0.15)
            confidence = min(confidence, 0.75)
            
            if self.streak_direction == TickDirection.UP:
                # After strong up streak, expect down
                return TickSignal(
                    direction=TickDirection.DOWN,
                    strength=TrendStrength.MODERATE,
                    confidence=confidence,
                    pattern=PatternType.REVERSAL_DOWN,
                    reason=f"Reversal expected after {self.current_streak} up ticks",
                    entry_price=current_price
                )
            else:
                # After strong down streak, expect up
                return TickSignal(
                    direction=TickDirection.UP,
                    strength=TrendStrength.MODERATE,
                    confidence=confidence,
                    pattern=PatternType.REVERSAL_UP,
                    reason=f"Reversal expected after {self.current_streak} down ticks",
                    entry_price=current_price
                )
        
        # Moderate streak - trend continuation possible
        elif self.MIN_STREAK_FOR_SIGNAL <= self.current_streak < self.STRONG_STREAK_THRESHOLD:
            if self.momentum_data and self.momentum_data.is_accelerating:
                # Momentum confirms trend
                confidence = 0.58 + (streak_factor * 0.10)
                
                if self.streak_direction == TickDirection.UP:
                    return TickSignal(
                        direction=TickDirection.UP,
                        strength=TrendStrength.MODERATE,
                        confidence=confidence,
                        pattern=PatternType.UPTREND,
                        reason=f"Trend continuation with {self.current_streak} up ticks + momentum",
                        entry_price=current_price
                    )
                else:
                    return TickSignal(
                        direction=TickDirection.DOWN,
                        strength=TrendStrength.MODERATE,
                        confidence=confidence,
                        pattern=PatternType.DOWNTREND,
                        reason=f"Trend continuation with {self.current_streak} down ticks + momentum",
                        entry_price=current_price
                    )
        
        return None
    
    def _analyze_momentum(self, current_price: float) -> Optional[TickSignal]:
        """Analyze momentum untuk signal generation"""
        if not self.momentum_data:
            return None
        
        mom = self.momentum_data
        
        # Strong momentum alignment across all windows
        if (mom.short_momentum > 0 and mom.medium_momentum > 0 and mom.long_momentum > 0):
            # All positive - strong uptrend
            if mom.is_accelerating:
                confidence = 0.65
                return TickSignal(
                    direction=TickDirection.UP,
                    strength=TrendStrength.STRONG,
                    confidence=confidence,
                    pattern=PatternType.UPTREND,
                    reason="Strong bullish momentum across all timeframes",
                    entry_price=current_price
                )
        
        elif (mom.short_momentum < 0 and mom.medium_momentum < 0 and mom.long_momentum < 0):
            # All negative - strong downtrend
            if mom.is_accelerating:
                confidence = 0.65
                return TickSignal(
                    direction=TickDirection.DOWN,
                    strength=TrendStrength.STRONG,
                    confidence=confidence,
                    pattern=PatternType.DOWNTREND,
                    reason="Strong bearish momentum across all timeframes",
                    entry_price=current_price
                )
        
        # Momentum divergence - potential reversal
        if mom.short_momentum > 0 and mom.long_momentum < 0:
            # Short up, long down - potential reversal up
            confidence = 0.58
            return TickSignal(
                direction=TickDirection.UP,
                strength=TrendStrength.WEAK,
                confidence=confidence,
                pattern=PatternType.REVERSAL_UP,
                reason="Short-term momentum diverging bullish from long-term",
                entry_price=current_price
            )
        
        elif mom.short_momentum < 0 and mom.long_momentum > 0:
            # Short down, long up - potential reversal down
            confidence = 0.58
            return TickSignal(
                direction=TickDirection.DOWN,
                strength=TrendStrength.WEAK,
                confidence=confidence,
                pattern=PatternType.REVERSAL_DOWN,
                reason="Short-term momentum diverging bearish from long-term",
                entry_price=current_price
            )
        
        return None
    
    def _analyze_pattern(self, pattern: PatternType, current_price: float) -> Optional[TickSignal]:
        """Generate signal based on detected pattern"""
        if pattern == PatternType.NO_PATTERN:
            return None
        
        if pattern == PatternType.CONSOLIDATION:
            # No clear direction in consolidation
            return None
        
        # Pattern-based signals sudah di-generate oleh streak dan momentum analysis
        return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current statistics"""
        up_pct = self.up_ticks / self.total_ticks * 100 if self.total_ticks > 0 else 50
        
        return {
            'total_ticks': self.total_ticks,
            'up_ticks': self.up_ticks,
            'down_ticks': self.down_ticks,
            'up_percentage': up_pct,
            'current_streak': self.current_streak,
            'streak_direction': self.streak_direction.value,
            'max_up_streak': self.max_up_streak,
            'max_down_streak': self.max_down_streak,
            'last_price': self.last_price,
            'ready': self.total_ticks >= self.MIN_TICKS_REQUIRED
        }
    
    def get_summary(self) -> str:
        """Get human-readable summary"""
        if self.total_ticks < 10:
            return "Insufficient data"
        
        stats = self.get_stats()
        pattern = self._detect_pattern()
        vol = self.get_volatility_data()
        
        lines = [
            f"📊 Tick Analysis ({self.total_ticks} ticks)",
            f"⬆️ Up: {stats['up_percentage']:.1f}% | ⬇️ Down: {100-stats['up_percentage']:.1f}%",
            f"📈 Current streak: {self.current_streak}x {self.streak_direction.value}",
            f"🎯 Pattern: {pattern.value}",
        ]
        
        if vol:
            vol_status = "HIGH" if vol.is_high_volatility else ("LOW" if vol.is_low_volatility else "NORMAL")
            lines.append(f"📉 Volatility: {vol_status}")
        
        if self.momentum_data:
            mom = self.momentum_data
            trend = "↑" if mom.medium_momentum > 0 else "↓"
            accel = "accelerating" if mom.is_accelerating else "decelerating"
            lines.append(f"🚀 Momentum: {trend} ({accel})")
        
        return "\n".join(lines)
    
    def clear_history(self) -> None:
        """Reset all history"""
        self.tick_history.clear()
        self.direction_history.clear()
        self.volatility_history.clear()
        
        self.total_ticks = 0
        self.last_price = 0.0
        self.current_streak = 0
        self.streak_direction = TickDirection.NEUTRAL
        self.max_up_streak = 0
        self.max_down_streak = 0
        self.up_ticks = 0
        self.down_ticks = 0
        self.momentum_data = None
        self.support_levels.clear()
        self.resistance_levels.clear()
        
        logger.info("🔄 Tick Trend Analyzer history cleared")
