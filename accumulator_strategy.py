"""
=============================================================
ACCUMULATOR STRATEGY - AMT Trading System
=============================================================
Modul ini mengimplementasikan strategi trading untuk 
Accumulator contracts (AMT - Accumulator Mode Trading).

Fitur:
1. Growth Rate Management (1%-5%)
2. Take Profit (TP) dan Stop Loss (SL) tracking
3. Trend strength analysis untuk entry
4. Volatility check untuk risk management
5. Dynamic growth rate recommendation

Referensi: binarybot.live/amt

Contract Type:
- Accumulator contracts dengan growth rate variable
- CALL/PUT direction based on trend analysis
- Auto-close pada TP/SL conditions

Optimal untuk:
- Strong trending markets
- Low-medium volatility conditions
- Synthetic Indices
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


class AccumulatorGrowthRate(Enum):
    """Growth rate options untuk Accumulator contracts"""
    RATE_1 = 0.01  # 1% growth rate
    RATE_2 = 0.02  # 2% growth rate
    RATE_3 = 0.03  # 3% growth rate
    RATE_4 = 0.04  # 4% growth rate
    RATE_5 = 0.05  # 5% growth rate
    
    @property
    def percentage(self) -> int:
        """Return growth rate as percentage integer"""
        return int(self.value * 100)
    
    @classmethod
    def from_percentage(cls, pct: int) -> 'AccumulatorGrowthRate':
        """Get growth rate from percentage value"""
        rate_map = {1: cls.RATE_1, 2: cls.RATE_2, 3: cls.RATE_3, 4: cls.RATE_4, 5: cls.RATE_5}
        return rate_map.get(pct, cls.RATE_1)


class AccumulatorStatus(Enum):
    """Status kontrak Accumulator"""
    ACTIVE = "ACTIVE"          # Contract is active and accumulating
    CLOSED = "CLOSED"          # Contract closed normally
    TAKE_PROFIT = "TAKE_PROFIT"  # Closed due to TP hit
    STOP_LOSS = "STOP_LOSS"    # Closed due to SL hit


class AccumulatorDirection(Enum):
    """Direction untuk Accumulator contract"""
    CALL = "CALL"  # Bullish - price will rise
    PUT = "PUT"    # Bearish - price will fall


@dataclass
class AccumulatorConfig:
    """Konfigurasi untuk Accumulator trading"""
    growth_rate: AccumulatorGrowthRate = AccumulatorGrowthRate.RATE_1
    take_profit_multiplier: float = 2.0  # TP at 2x stake (100% profit)
    stop_loss_amount: float = 0.5        # SL at 50% of stake
    max_ticks: int = 100                 # Maximum ticks before auto-close
    
    def __post_init__(self):
        """Validate config values"""
        if self.take_profit_multiplier < 1.1:
            self.take_profit_multiplier = 1.1
        if self.stop_loss_amount < 0.1:
            self.stop_loss_amount = 0.1
        if self.stop_loss_amount > 0.9:
            self.stop_loss_amount = 0.9
        if self.max_ticks < 10:
            self.max_ticks = 10


@dataclass
class AccumulatorSignal:
    """Signal hasil analisis Accumulator Strategy"""
    direction: AccumulatorDirection
    confidence: float  # 0.0 - 1.0
    growth_rate: AccumulatorGrowthRate
    entry_price: float
    reason: str
    timestamp: datetime = field(default_factory=datetime.now)
    
    def __str__(self):
        return (f"ACC {self.direction.value} @ {self.entry_price:.5f} "
                f"(rate: {self.growth_rate.percentage}%, conf: {self.confidence:.1%})")
    
    def is_valid(self, min_confidence: float = 0.65) -> bool:
        """Check if signal meets minimum confidence threshold"""
        return self.confidence >= min_confidence


@dataclass
class AccumulatorAnalysisResult:
    """Hasil lengkap analisis Accumulator Strategy"""
    signal: Optional[AccumulatorSignal]
    trend_strength: float              # 0.0 - 1.0, kekuatan trend
    volatility_check: bool             # True = safe, False = too volatile
    recommended_rate: AccumulatorGrowthRate
    current_price: float = 0.0
    tick_count: int = 0
    trend_direction: str = "NEUTRAL"   # UP, DOWN, NEUTRAL
    volatility_score: float = 0.0      # 0.0 - 1.0
    analysis_note: str = ""


class AccumulatorStrategy:
    """
    Accumulator Trading Strategy (AMT)
    
    Menganalisis market conditions untuk menghasilkan sinyal
    trading Accumulator contracts dengan growth rate yang optimal.
    
    Logic:
    - Strong trend = higher growth rate allowed (more risk, more reward)
    - High volatility = lower growth rate recommended (safer)
    - TP default: 2x stake (100% profit)
    - SL default: 50% stake
    - Minimum confidence: 0.65 (65%)
    """
    
    # Configuration
    MIN_TICKS_REQUIRED = 30      # Minimum ticks untuk analisis valid
    MAX_TICK_HISTORY = 500       # Maximum tick history yang disimpan
    
    # Trend analysis settings
    TREND_LOOKBACK_SHORT = 10    # Short-term trend window
    TREND_LOOKBACK_MEDIUM = 25   # Medium-term trend window
    TREND_LOOKBACK_LONG = 50     # Long-term trend window
    
    # Volatility settings
    VOLATILITY_WINDOW = 20       # Window untuk volatility calculation
    HIGH_VOLATILITY_THRESHOLD = 0.70  # Above this = high volatility
    LOW_VOLATILITY_THRESHOLD = 0.30   # Below this = low volatility
    
    # Confidence thresholds
    MIN_CONFIDENCE = 0.65        # Minimum confidence untuk generate signal
    HIGH_CONFIDENCE = 0.80       # High confidence threshold
    
    # Trend strength thresholds
    STRONG_TREND_THRESHOLD = 0.70    # Strong trend
    MODERATE_TREND_THRESHOLD = 0.50  # Moderate trend
    WEAK_TREND_THRESHOLD = 0.30      # Weak trend
    
    # Default TP/SL
    DEFAULT_TP_MULTIPLIER = 2.0  # 2x stake
    DEFAULT_SL_AMOUNT = 0.5      # 50% of stake
    
    def __init__(self, config: Optional[AccumulatorConfig] = None):
        """
        Inisialisasi Accumulator Strategy.
        
        Args:
            config: Optional AccumulatorConfig untuk custom settings
        """
        self.config = config or AccumulatorConfig()
        
        # Tick history storage
        self.tick_history: deque = deque(maxlen=self.MAX_TICK_HISTORY)
        self.price_changes: deque = deque(maxlen=self.MAX_TICK_HISTORY)
        
        # State tracking
        self.total_ticks: int = 0
        self.last_price: float = 0.0
        
        # Trend tracking
        self.up_moves: int = 0
        self.down_moves: int = 0
        self.consecutive_up: int = 0
        self.consecutive_down: int = 0
        
        # Volatility tracking
        self.volatility_history: deque = deque(maxlen=100)
        
        # Analysis cache
        self._last_analysis: Optional[AccumulatorAnalysisResult] = None
        self._last_signal: Optional[AccumulatorSignal] = None
        
        logger.info("📊 Accumulator Strategy initialized")
    
    def add_tick(self, price: float) -> None:
        """
        Tambahkan tick baru dan update analisis.
        
        Args:
            price: Harga tick baru
        """
        if not self._is_valid_price(price):
            logger.warning(f"Invalid price received: {price}")
            return
        
        self.tick_history.append(price)
        self.total_ticks += 1
        
        # Calculate price change
        if self.last_price > 0:
            change = price - self.last_price
            pct_change = change / self.last_price
            self.price_changes.append(pct_change)
            
            # Update move tracking
            if change > 0:
                self.up_moves += 1
                self.consecutive_up += 1
                self.consecutive_down = 0
            elif change < 0:
                self.down_moves += 1
                self.consecutive_down += 1
                self.consecutive_up = 0
            
            # Update volatility tracking
            self.volatility_history.append(abs(pct_change))
        
        self.last_price = price
    
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
    
    def _calculate_trend_strength(self) -> Tuple[float, str]:
        """
        Hitung kekuatan trend untuk entry decision.
        
        Returns:
            Tuple[float, str]: (trend_strength 0.0-1.0, direction UP/DOWN/NEUTRAL)
        """
        if len(self.tick_history) < self.MIN_TICKS_REQUIRED:
            return (0.0, "NEUTRAL")
        
        prices = list(self.tick_history)
        
        # Calculate trend dari multiple timeframes
        short_trend = self._calculate_direction_ratio(prices[-self.TREND_LOOKBACK_SHORT:])
        medium_trend = self._calculate_direction_ratio(prices[-self.TREND_LOOKBACK_MEDIUM:]) if len(prices) >= self.TREND_LOOKBACK_MEDIUM else short_trend
        long_trend = self._calculate_direction_ratio(prices[-self.TREND_LOOKBACK_LONG:]) if len(prices) >= self.TREND_LOOKBACK_LONG else medium_trend
        
        # Weighted average (recent = more weight)
        avg_ratio = (short_trend * 0.5) + (medium_trend * 0.3) + (long_trend * 0.2)
        
        # Calculate strength (distance from 0.5)
        strength = abs(avg_ratio - 0.5) * 2  # Scale to 0-1
        
        # Determine direction
        if avg_ratio > 0.55:
            direction = "UP"
        elif avg_ratio < 0.45:
            direction = "DOWN"
        else:
            direction = "NEUTRAL"
        
        # Boost strength if consecutive moves align
        if direction == "UP" and self.consecutive_up >= 3:
            strength = min(strength * 1.2, 1.0)
        elif direction == "DOWN" and self.consecutive_down >= 3:
            strength = min(strength * 1.2, 1.0)
        
        return (strength, direction)
    
    def _calculate_direction_ratio(self, prices: List[float]) -> float:
        """Calculate ratio of up moves vs total moves"""
        if len(prices) < 2:
            return 0.5
        
        up_count = 0
        total_moves = 0
        
        for i in range(1, len(prices)):
            if prices[i] > prices[i-1]:
                up_count += 1
                total_moves += 1
            elif prices[i] < prices[i-1]:
                total_moves += 1
        
        if total_moves == 0:
            return 0.5
        
        return up_count / total_moves
    
    def _check_volatility(self) -> Tuple[bool, float]:
        """
        Check volatility untuk determine safe entry.
        
        Returns:
            Tuple[bool, float]: (is_safe_entry, volatility_score 0.0-1.0)
        """
        if len(self.volatility_history) < 10:
            return (True, 0.5)  # Not enough data, assume moderate
        
        vol_list = list(self.volatility_history)
        
        # Calculate current volatility metrics
        current_vol = sum(vol_list[-10:]) / 10  # Average of last 10
        avg_vol = sum(vol_list) / len(vol_list)
        max_vol = max(vol_list) if vol_list else 0
        
        # Normalize to 0-1 scale
        if max_vol > 0:
            vol_score = current_vol / max_vol
        else:
            vol_score = 0.5
        
        # Clamp to valid range
        vol_score = max(0.0, min(1.0, vol_score))
        
        # Determine if safe for entry
        is_safe = vol_score < self.HIGH_VOLATILITY_THRESHOLD
        
        return (is_safe, vol_score)
    
    def _recommend_growth_rate(self, trend_strength: float, volatility_score: float) -> AccumulatorGrowthRate:
        """
        Recommend growth rate berdasarkan market condition.
        
        Logic:
        - Strong trend + Low volatility = Higher rate (4-5%)
        - Strong trend + High volatility = Medium rate (3%)
        - Moderate trend + Low volatility = Medium rate (2-3%)
        - Moderate trend + High volatility = Low rate (1-2%)
        - Weak trend = Low rate (1%)
        
        Args:
            trend_strength: 0.0-1.0
            volatility_score: 0.0-1.0 (higher = more volatile)
            
        Returns:
            AccumulatorGrowthRate recommendation
        """
        # Calculate composite score
        # Higher trend strength = higher rate allowed
        # Lower volatility = higher rate allowed
        trend_factor = trend_strength
        safety_factor = 1.0 - volatility_score
        
        composite = (trend_factor * 0.6) + (safety_factor * 0.4)
        
        # Map to growth rate
        if composite >= 0.80:
            return AccumulatorGrowthRate.RATE_5
        elif composite >= 0.65:
            return AccumulatorGrowthRate.RATE_4
        elif composite >= 0.50:
            return AccumulatorGrowthRate.RATE_3
        elif composite >= 0.35:
            return AccumulatorGrowthRate.RATE_2
        else:
            return AccumulatorGrowthRate.RATE_1
    
    def _calculate_confidence(self, trend_strength: float, volatility_score: float, 
                             trend_direction: str) -> float:
        """
        Calculate signal confidence.
        
        Args:
            trend_strength: 0.0-1.0
            volatility_score: 0.0-1.0
            trend_direction: UP/DOWN/NEUTRAL
            
        Returns:
            Confidence score 0.0-1.0
        """
        # Base confidence from trend strength
        base_conf = trend_strength * 0.6
        
        # Volatility adjustment (lower vol = higher confidence)
        vol_factor = (1.0 - volatility_score) * 0.25
        
        # Direction clarity bonus
        direction_bonus = 0.0
        if trend_direction != "NEUTRAL":
            direction_bonus = 0.10
            
            # Extra bonus for strong consecutive moves
            if trend_direction == "UP" and self.consecutive_up >= 4:
                direction_bonus += 0.05
            elif trend_direction == "DOWN" and self.consecutive_down >= 4:
                direction_bonus += 0.05
        
        # Calculate final confidence
        confidence = base_conf + vol_factor + direction_bonus
        
        # Clamp to valid range
        return max(0.0, min(1.0, confidence))
    
    def analyze(self) -> Optional[AccumulatorAnalysisResult]:
        """
        Perform full analysis dan generate AccumulatorAnalysisResult.
        
        Returns:
            AccumulatorAnalysisResult dengan signal dan recommendations
        """
        if self.total_ticks < self.MIN_TICKS_REQUIRED:
            return None
        
        if len(self.tick_history) < 2:
            return None
        
        current_price = self.tick_history[-1]
        
        # 1. Calculate trend strength
        trend_strength, trend_direction = self._calculate_trend_strength()
        
        # 2. Check volatility
        is_safe, volatility_score = self._check_volatility()
        
        # 3. Recommend growth rate
        recommended_rate = self._recommend_growth_rate(trend_strength, volatility_score)
        
        # 4. Calculate confidence
        confidence = self._calculate_confidence(trend_strength, volatility_score, trend_direction)
        
        # 5. Generate signal if conditions are met
        signal = None
        analysis_note = ""
        
        if trend_direction != "NEUTRAL" and confidence >= self.MIN_CONFIDENCE:
            if is_safe:
                direction = AccumulatorDirection.CALL if trend_direction == "UP" else AccumulatorDirection.PUT
                
                reason = self._generate_signal_reason(
                    trend_direction, trend_strength, volatility_score, 
                    recommended_rate, self.consecutive_up, self.consecutive_down
                )
                
                signal = AccumulatorSignal(
                    direction=direction,
                    confidence=confidence,
                    growth_rate=recommended_rate,
                    entry_price=current_price,
                    reason=reason
                )
                
                analysis_note = f"Signal generated: {direction.value} with {recommended_rate.percentage}% rate"
            else:
                analysis_note = "High volatility - entry blocked for safety"
        else:
            if trend_direction == "NEUTRAL":
                analysis_note = "No clear trend direction detected"
            else:
                analysis_note = f"Confidence too low ({confidence:.1%} < {self.MIN_CONFIDENCE:.1%})"
        
        # Cache and return result
        result = AccumulatorAnalysisResult(
            signal=signal,
            trend_strength=trend_strength,
            volatility_check=is_safe,
            recommended_rate=recommended_rate,
            current_price=current_price,
            tick_count=self.total_ticks,
            trend_direction=trend_direction,
            volatility_score=volatility_score,
            analysis_note=analysis_note
        )
        
        self._last_analysis = result
        if signal:
            self._last_signal = signal
        
        return result
    
    def _generate_signal_reason(self, trend_direction: str, trend_strength: float,
                                volatility_score: float, growth_rate: AccumulatorGrowthRate,
                                consec_up: int, consec_down: int) -> str:
        """Generate human-readable reason for signal"""
        reasons = []
        
        # Trend strength description
        if trend_strength >= self.STRONG_TREND_THRESHOLD:
            reasons.append(f"Strong {trend_direction.lower()} trend ({trend_strength:.0%})")
        elif trend_strength >= self.MODERATE_TREND_THRESHOLD:
            reasons.append(f"Moderate {trend_direction.lower()} trend ({trend_strength:.0%})")
        else:
            reasons.append(f"Weak {trend_direction.lower()} trend ({trend_strength:.0%})")
        
        # Consecutive moves
        if consec_up >= 3 and trend_direction == "UP":
            reasons.append(f"{consec_up} consecutive up ticks")
        elif consec_down >= 3 and trend_direction == "DOWN":
            reasons.append(f"{consec_down} consecutive down ticks")
        
        # Volatility status
        if volatility_score < self.LOW_VOLATILITY_THRESHOLD:
            reasons.append("low volatility (safe)")
        elif volatility_score < self.HIGH_VOLATILITY_THRESHOLD:
            reasons.append("moderate volatility")
        
        # Growth rate reasoning
        reasons.append(f"recommended rate: {growth_rate.percentage}%")
        
        return "; ".join(reasons)
    
    def get_signal_for_trading(self) -> Optional[AccumulatorSignal]:
        """
        Get trading signal dari latest analysis.
        
        Returns:
            AccumulatorSignal jika ada signal valid, None jika tidak
        """
        result = self.analyze()
        
        if result is None:
            return None
        
        if result.signal and result.signal.is_valid(self.MIN_CONFIDENCE):
            return result.signal
        
        return None
    
    def should_take_profit(self, current_value: float, entry_stake: float) -> bool:
        """
        Check apakah should take profit.
        
        Args:
            current_value: Current contract value
            entry_stake: Original stake amount
            
        Returns:
            True jika should take profit
        """
        if entry_stake <= 0:
            return False
        
        tp_threshold = entry_stake * self.config.take_profit_multiplier
        return current_value >= tp_threshold
    
    def should_stop_loss(self, current_value: float, entry_stake: float) -> bool:
        """
        Check apakah should stop loss.
        
        Args:
            current_value: Current contract value
            entry_stake: Original stake amount
            
        Returns:
            True jika should stop loss
        """
        if entry_stake <= 0:
            return False
        
        sl_threshold = entry_stake * self.config.stop_loss_amount
        return current_value <= sl_threshold
    
    def get_tp_sl_levels(self, entry_stake: float) -> Tuple[float, float]:
        """
        Get Take Profit dan Stop Loss levels.
        
        Args:
            entry_stake: Original stake amount
            
        Returns:
            Tuple[float, float]: (take_profit_level, stop_loss_level)
        """
        tp_level = entry_stake * self.config.take_profit_multiplier
        sl_level = entry_stake * self.config.stop_loss_amount
        return (tp_level, sl_level)
    
    def reset(self) -> None:
        """Reset strategy state untuk fresh start"""
        self.tick_history.clear()
        self.price_changes.clear()
        self.volatility_history.clear()
        
        self.total_ticks = 0
        self.last_price = 0.0
        self.up_moves = 0
        self.down_moves = 0
        self.consecutive_up = 0
        self.consecutive_down = 0
        
        self._last_analysis = None
        self._last_signal = None
        
        logger.info("📊 Accumulator Strategy reset")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current strategy statistics"""
        total_moves = self.up_moves + self.down_moves
        up_ratio = self.up_moves / total_moves if total_moves > 0 else 0.5
        
        return {
            "total_ticks": self.total_ticks,
            "up_moves": self.up_moves,
            "down_moves": self.down_moves,
            "up_ratio": up_ratio,
            "consecutive_up": self.consecutive_up,
            "consecutive_down": self.consecutive_down,
            "current_price": self.last_price,
            "config_tp_multiplier": self.config.take_profit_multiplier,
            "config_sl_amount": self.config.stop_loss_amount,
            "config_growth_rate": self.config.growth_rate.percentage
        }


# Utility functions for external use
def create_accumulator_config(
    growth_rate_pct: int = 1,
    tp_multiplier: float = 2.0,
    sl_amount: float = 0.5,
    max_ticks: int = 100
) -> AccumulatorConfig:
    """
    Create AccumulatorConfig dengan parameter yang mudah digunakan.
    
    Args:
        growth_rate_pct: Growth rate percentage (1-5)
        tp_multiplier: Take profit multiplier (default 2.0 = 2x stake)
        sl_amount: Stop loss as fraction of stake (default 0.5 = 50%)
        max_ticks: Maximum ticks before auto-close
        
    Returns:
        AccumulatorConfig instance
    """
    growth_rate = AccumulatorGrowthRate.from_percentage(growth_rate_pct)
    
    return AccumulatorConfig(
        growth_rate=growth_rate,
        take_profit_multiplier=tp_multiplier,
        stop_loss_amount=sl_amount,
        max_ticks=max_ticks
    )


if __name__ == "__main__":
    # Simple test
    print("Testing Accumulator Strategy...")
    
    strategy = AccumulatorStrategy()
    
    # Simulate uptrend
    base_price = 1000.0
    for i in range(50):
        # Simulate slight uptrend with some noise
        noise = (i % 3 - 1) * 0.5
        price = base_price + (i * 0.3) + noise
        strategy.add_tick(price)
    
    # Analyze
    result = strategy.analyze()
    
    if result:
        print(f"\n📊 Analysis Result:")
        print(f"   Trend Direction: {result.trend_direction}")
        print(f"   Trend Strength: {result.trend_strength:.1%}")
        print(f"   Volatility Safe: {result.volatility_check}")
        print(f"   Volatility Score: {result.volatility_score:.1%}")
        print(f"   Recommended Rate: {result.recommended_rate.percentage}%")
        print(f"   Note: {result.analysis_note}")
        
        if result.signal:
            print(f"\n🎯 Signal: {result.signal}")
        else:
            print("\n⏸️  No signal generated")
    
    # Test TP/SL
    tp_level, sl_level = strategy.get_tp_sl_levels(10.0)
    print(f"\n💰 For $10 stake:")
    print(f"   Take Profit Level: ${tp_level:.2f}")
    print(f"   Stop Loss Level: ${sl_level:.2f}")
    
    # Test should_take_profit and should_stop_loss
    print(f"\n🔍 TP/SL Check (stake=$10):")
    print(f"   Should TP at $20: {strategy.should_take_profit(20.0, 10.0)}")
    print(f"   Should TP at $15: {strategy.should_take_profit(15.0, 10.0)}")
    print(f"   Should SL at $5: {strategy.should_stop_loss(5.0, 10.0)}")
    print(f"   Should SL at $6: {strategy.should_stop_loss(6.0, 10.0)}")
    
    print("\n✅ Accumulator Strategy test complete!")
