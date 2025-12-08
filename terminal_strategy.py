"""
=============================================================
TERMINAL STRATEGY - Smart Analysis Trading System
=============================================================
Modul ini mengimplementasikan strategi trading berbasis 
terminal.nextrader.live dengan Smart Analysis dan Hybrid Recovery.

Fitur:
1. Smart Analysis dengan 80% probability scoring
2. 4 level risiko: Low, Medium, High, Very High
3. Hybrid Recovery system (martingale + anti-martingale)
4. Multi-indicator probability weighting

Probability Scoring:
- RSI weight: 25%
- EMA crossover weight: 25%
- MACD signal weight: 20%
- Stochastic weight: 15%
- ADX strength weight: 15%

Minimum confidence untuk trade: 0.80 (80%)
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


class RiskLevel(Enum):
    """Level risiko trading"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"


class RecoveryMode(Enum):
    """Mode recovery untuk money management"""
    MARTINGALE = "MARTINGALE"
    ANTI_MARTINGALE = "ANTI_MARTINGALE"
    HYBRID = "HYBRID"


class SignalDirection(Enum):
    """Arah sinyal trading"""
    CALL = "CALL"
    PUT = "PUT"
    WAIT = "WAIT"


@dataclass
class TerminalSignal:
    """Hasil sinyal Terminal Strategy"""
    direction: SignalDirection
    confidence: float
    risk_level: RiskLevel
    recovery_mode: RecoveryMode
    reason: str
    
    def __str__(self):
        return f"{self.direction.value} (conf: {self.confidence:.1%}, risk: {self.risk_level.value})"


@dataclass
class TerminalAnalysisResult:
    """Hasil lengkap analisis Terminal Strategy"""
    signal: Optional[TerminalSignal]
    probability: float
    indicators_used: Dict[str, float]
    risk_band: str
    rsi_score: float = 0.0
    ema_score: float = 0.0
    macd_score: float = 0.0
    stoch_score: float = 0.0
    adx_score: float = 0.0
    volatility: float = 0.0
    tick_count: int = 0


class TerminalStrategy:
    """
    Terminal Strategy - Smart Analysis Trading System
    
    Menganalisis multiple indicators untuk menghasilkan sinyal trading
    dengan 80% minimum probability scoring.
    """
    
    MIN_TICKS_REQUIRED = 50
    MAX_TICK_HISTORY = 500
    
    RSI_PERIOD = 14
    RSI_OVERSOLD = 30
    RSI_OVERBOUGHT = 70
    
    EMA_FAST_PERIOD = 9
    EMA_SLOW_PERIOD = 21
    
    MACD_FAST = 12
    MACD_SLOW = 26
    MACD_SIGNAL = 9
    
    STOCH_PERIOD = 14
    STOCH_SMOOTH = 3
    STOCH_OVERSOLD = 20
    STOCH_OVERBOUGHT = 80
    
    ADX_PERIOD = 14
    ADX_STRONG_TREND = 25
    ADX_WEAK_TREND = 20
    
    VOLATILITY_PERIOD = 20
    
    RSI_WEIGHT = 0.25
    EMA_WEIGHT = 0.25
    MACD_WEIGHT = 0.20
    STOCH_WEIGHT = 0.15
    ADX_WEIGHT = 0.15
    
    MIN_CONFIDENCE = 0.80
    
    VOLATILITY_LOW = 0.001
    VOLATILITY_MEDIUM = 0.003
    VOLATILITY_HIGH = 0.005
    
    def __init__(self):
        """Inisialisasi Terminal Strategy"""
        self.tick_history: deque = deque(maxlen=self.MAX_TICK_HISTORY)
        self.high_history: deque = deque(maxlen=self.MAX_TICK_HISTORY)
        self.low_history: deque = deque(maxlen=self.MAX_TICK_HISTORY)
        self.total_ticks: int = 0
        
        self._ema_fast_cache: Optional[float] = None
        self._ema_slow_cache: Optional[float] = None
        self._macd_ema_fast_cache: Optional[float] = None
        self._macd_ema_slow_cache: Optional[float] = None
        self._macd_signal_cache: Optional[float] = None
        
        self._rsi_gains: deque = deque(maxlen=self.RSI_PERIOD)
        self._rsi_losses: deque = deque(maxlen=self.RSI_PERIOD)
        
        self._last_price: float = 0.0
        
        self.consecutive_wins: int = 0
        self.consecutive_losses: int = 0
        
        logger.info("🖥️ Terminal Strategy initialized")
    
    def add_tick(self, price: float) -> None:
        """
        Tambahkan tick baru dan update analisis.
        
        Args:
            price: Harga tick baru
        """
        if not self._is_valid_price(price):
            return
        
        self.tick_history.append(price)
        self.total_ticks += 1
        
        if len(self.tick_history) > 1:
            prev_price = self.tick_history[-2]
            high = max(price, prev_price)
            low = min(price, prev_price)
            
            change = price - prev_price
            if change > 0:
                self._rsi_gains.append(change)
                self._rsi_losses.append(0)
            else:
                self._rsi_gains.append(0)
                self._rsi_losses.append(abs(change))
        else:
            high = price
            low = price
        
        self.high_history.append(high)
        self.low_history.append(low)
        
        self._last_price = price
        
        if self.total_ticks % 10 == 0:
            self._update_indicator_caches()
    
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
    
    def _update_indicator_caches(self) -> None:
        """Update cached indicator values"""
        if len(self.tick_history) >= self.EMA_FAST_PERIOD:
            self._ema_fast_cache = self._calculate_ema(list(self.tick_history), self.EMA_FAST_PERIOD)
        
        if len(self.tick_history) >= self.EMA_SLOW_PERIOD:
            self._ema_slow_cache = self._calculate_ema(list(self.tick_history), self.EMA_SLOW_PERIOD)
    
    def _calculate_ema(self, prices: List[float], period: int) -> float:
        """Calculate Exponential Moving Average"""
        if len(prices) < period:
            return sum(prices) / len(prices) if prices else 0.0
        
        k = 2 / (period + 1)
        ema = sum(prices[:period]) / period
        
        for price in prices[period:]:
            ema = price * k + ema * (1 - k)
        
        return ema
    
    def _calculate_rsi(self) -> float:
        """Calculate RSI (Relative Strength Index)"""
        if len(self._rsi_gains) < self.RSI_PERIOD:
            return 50.0
        
        avg_gain = sum(self._rsi_gains) / len(self._rsi_gains)
        avg_loss = sum(self._rsi_losses) / len(self._rsi_losses)
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def _calculate_macd(self) -> Tuple[float, float, float]:
        """
        Calculate MACD (Moving Average Convergence Divergence)
        
        Returns:
            (macd_line, signal_line, histogram)
        """
        prices = list(self.tick_history)
        
        if len(prices) < self.MACD_SLOW:
            return 0.0, 0.0, 0.0
        
        ema_fast = self._calculate_ema(prices, self.MACD_FAST)
        ema_slow = self._calculate_ema(prices, self.MACD_SLOW)
        
        macd_line = ema_fast - ema_slow
        
        macd_values = []
        for i in range(self.MACD_SLOW, len(prices) + 1):
            subset = prices[:i]
            fast = self._calculate_ema(subset, self.MACD_FAST)
            slow = self._calculate_ema(subset, self.MACD_SLOW)
            macd_values.append(fast - slow)
        
        if len(macd_values) >= self.MACD_SIGNAL:
            signal_line = self._calculate_ema(macd_values, self.MACD_SIGNAL)
        else:
            signal_line = sum(macd_values) / len(macd_values) if macd_values else 0.0
        
        histogram = macd_line - signal_line
        
        return macd_line, signal_line, histogram
    
    def _calculate_stochastic(self) -> Tuple[float, float]:
        """
        Calculate Stochastic Oscillator
        
        Returns:
            (stoch_k, stoch_d)
        """
        if len(self.tick_history) < self.STOCH_PERIOD:
            return 50.0, 50.0
        
        prices = list(self.tick_history)[-self.STOCH_PERIOD:]
        highs = list(self.high_history)[-self.STOCH_PERIOD:]
        lows = list(self.low_history)[-self.STOCH_PERIOD:]
        
        highest_high = max(highs)
        lowest_low = min(lows)
        current_price = prices[-1]
        
        if highest_high == lowest_low:
            stoch_k = 50.0
        else:
            stoch_k = ((current_price - lowest_low) / (highest_high - lowest_low)) * 100
        
        k_values = []
        for i in range(max(0, len(self.tick_history) - self.STOCH_SMOOTH), len(self.tick_history)):
            subset_prices = list(self.tick_history)[max(0, i - self.STOCH_PERIOD + 1):i + 1]
            subset_highs = list(self.high_history)[max(0, i - self.STOCH_PERIOD + 1):i + 1]
            subset_lows = list(self.low_history)[max(0, i - self.STOCH_PERIOD + 1):i + 1]
            
            if not subset_prices:
                continue
                
            hh = max(subset_highs) if subset_highs else subset_prices[-1]
            ll = min(subset_lows) if subset_lows else subset_prices[-1]
            cp = subset_prices[-1]
            
            if hh != ll:
                k_values.append(((cp - ll) / (hh - ll)) * 100)
            else:
                k_values.append(50.0)
        
        stoch_d = sum(k_values) / len(k_values) if k_values else stoch_k
        
        return stoch_k, stoch_d
    
    def _calculate_adx(self) -> Tuple[float, float, float]:
        """
        Calculate ADX (Average Directional Index)
        
        Returns:
            (adx, plus_di, minus_di)
        """
        if len(self.tick_history) < self.ADX_PERIOD + 1:
            return 0.0, 0.0, 0.0
        
        prices = list(self.tick_history)
        highs = list(self.high_history)
        lows = list(self.low_history)
        
        plus_dm_list = []
        minus_dm_list = []
        tr_list = []
        
        for i in range(1, len(prices)):
            high_diff = highs[i] - highs[i-1] if i < len(highs) else 0
            low_diff = lows[i-1] - lows[i] if i < len(lows) else 0
            
            plus_dm = high_diff if high_diff > low_diff and high_diff > 0 else 0
            minus_dm = low_diff if low_diff > high_diff and low_diff > 0 else 0
            
            plus_dm_list.append(plus_dm)
            minus_dm_list.append(minus_dm)
            
            tr = max(
                highs[i] - lows[i] if i < len(highs) and i < len(lows) else 0,
                abs(highs[i] - prices[i-1]) if i < len(highs) else 0,
                abs(lows[i] - prices[i-1]) if i < len(lows) else 0
            )
            tr_list.append(tr)
        
        if len(tr_list) < self.ADX_PERIOD:
            return 0.0, 0.0, 0.0
        
        smoothed_tr = sum(tr_list[-self.ADX_PERIOD:])
        smoothed_plus_dm = sum(plus_dm_list[-self.ADX_PERIOD:])
        smoothed_minus_dm = sum(minus_dm_list[-self.ADX_PERIOD:])
        
        if smoothed_tr == 0:
            return 0.0, 0.0, 0.0
        
        plus_di = (smoothed_plus_dm / smoothed_tr) * 100
        minus_di = (smoothed_minus_dm / smoothed_tr) * 100
        
        di_sum = plus_di + minus_di
        if di_sum == 0:
            dx = 0.0
        else:
            dx = (abs(plus_di - minus_di) / di_sum) * 100
        
        adx = dx
        
        return adx, plus_di, minus_di
    
    def _calculate_volatility(self) -> float:
        """Calculate price volatility"""
        if len(self.tick_history) < self.VOLATILITY_PERIOD:
            return 0.0
        
        prices = list(self.tick_history)[-self.VOLATILITY_PERIOD:]
        
        returns = []
        for i in range(1, len(prices)):
            if prices[i-1] != 0:
                ret = (prices[i] - prices[i-1]) / prices[i-1]
                returns.append(ret)
        
        if not returns:
            return 0.0
        
        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
        volatility = math.sqrt(variance)
        
        return volatility
    
    def _calculate_probability(self) -> Dict[str, float]:
        """
        Hitung probability scoring dari multiple indicators.
        
        Returns:
            Dictionary dengan scores untuk setiap indicator dan total
        """
        scores = {
            'rsi': 0.0,
            'ema': 0.0,
            'macd': 0.0,
            'stoch': 0.0,
            'adx': 0.0,
            'total': 0.0,
            'direction': 'WAIT'
        }
        
        if self.total_ticks < self.MIN_TICKS_REQUIRED:
            return scores
        
        rsi = self._calculate_rsi()
        rsi_score = 0.0
        rsi_direction = 'NEUTRAL'
        
        if rsi <= self.RSI_OVERSOLD:
            rsi_score = min(1.0, (self.RSI_OVERSOLD - rsi) / self.RSI_OVERSOLD + 0.5)
            rsi_direction = 'CALL'
        elif rsi >= self.RSI_OVERBOUGHT:
            rsi_score = min(1.0, (rsi - self.RSI_OVERBOUGHT) / (100 - self.RSI_OVERBOUGHT) + 0.5)
            rsi_direction = 'PUT'
        else:
            distance_to_extreme = min(abs(rsi - self.RSI_OVERSOLD), abs(rsi - self.RSI_OVERBOUGHT))
            rsi_score = max(0.0, 0.3 - distance_to_extreme / 100)
        
        scores['rsi'] = rsi_score
        
        prices = list(self.tick_history)
        ema_fast = self._calculate_ema(prices, self.EMA_FAST_PERIOD)
        ema_slow = self._calculate_ema(prices, self.EMA_SLOW_PERIOD)
        
        ema_score = 0.0
        ema_direction = 'NEUTRAL'
        
        if ema_fast > ema_slow:
            diff_pct = (ema_fast - ema_slow) / ema_slow if ema_slow != 0 else 0
            ema_score = min(1.0, 0.5 + diff_pct * 100)
            ema_direction = 'CALL'
        elif ema_fast < ema_slow:
            diff_pct = (ema_slow - ema_fast) / ema_slow if ema_slow != 0 else 0
            ema_score = min(1.0, 0.5 + diff_pct * 100)
            ema_direction = 'PUT'
        
        scores['ema'] = ema_score
        
        macd_line, signal_line, histogram = self._calculate_macd()
        macd_score = 0.0
        macd_direction = 'NEUTRAL'
        
        if histogram > 0:
            macd_score = min(1.0, 0.5 + abs(histogram) * 1000)
            macd_direction = 'CALL'
        elif histogram < 0:
            macd_score = min(1.0, 0.5 + abs(histogram) * 1000)
            macd_direction = 'PUT'
        
        scores['macd'] = macd_score
        
        stoch_k, stoch_d = self._calculate_stochastic()
        stoch_score = 0.0
        stoch_direction = 'NEUTRAL'
        
        if stoch_k <= self.STOCH_OVERSOLD:
            stoch_score = min(1.0, (self.STOCH_OVERSOLD - stoch_k) / self.STOCH_OVERSOLD + 0.5)
            stoch_direction = 'CALL'
        elif stoch_k >= self.STOCH_OVERBOUGHT:
            stoch_score = min(1.0, (stoch_k - self.STOCH_OVERBOUGHT) / (100 - self.STOCH_OVERBOUGHT) + 0.5)
            stoch_direction = 'PUT'
        else:
            if stoch_k > stoch_d:
                stoch_score = 0.4
                stoch_direction = 'CALL'
            elif stoch_k < stoch_d:
                stoch_score = 0.4
                stoch_direction = 'PUT'
        
        scores['stoch'] = stoch_score
        
        adx, plus_di, minus_di = self._calculate_adx()
        adx_score = 0.0
        adx_direction = 'NEUTRAL'
        
        if adx >= self.ADX_STRONG_TREND:
            adx_score = min(1.0, adx / 50)
            if plus_di > minus_di:
                adx_direction = 'CALL'
            else:
                adx_direction = 'PUT'
        elif adx >= self.ADX_WEAK_TREND:
            adx_score = adx / 50
            if plus_di > minus_di:
                adx_direction = 'CALL'
            else:
                adx_direction = 'PUT'
        
        scores['adx'] = adx_score
        
        call_count = sum(1 for d in [rsi_direction, ema_direction, macd_direction, stoch_direction, adx_direction] if d == 'CALL')
        put_count = sum(1 for d in [rsi_direction, ema_direction, macd_direction, stoch_direction, adx_direction] if d == 'PUT')
        
        if call_count > put_count:
            direction = 'CALL'
        elif put_count > call_count:
            direction = 'PUT'
        else:
            direction = 'WAIT'
        
        total_probability = (
            scores['rsi'] * self.RSI_WEIGHT +
            scores['ema'] * self.EMA_WEIGHT +
            scores['macd'] * self.MACD_WEIGHT +
            scores['stoch'] * self.STOCH_WEIGHT +
            scores['adx'] * self.ADX_WEIGHT
        )
        
        agreement_bonus = max(call_count, put_count) / 5 * 0.1
        scores['total'] = min(1.0, total_probability + agreement_bonus)
        scores['direction'] = direction
        
        return scores
    
    def _determine_risk_level(self) -> RiskLevel:
        """
        Tentukan risk level berdasarkan volatility.
        
        Returns:
            RiskLevel enum value
        """
        volatility = self._calculate_volatility()
        
        if volatility <= self.VOLATILITY_LOW:
            return RiskLevel.LOW
        elif volatility <= self.VOLATILITY_MEDIUM:
            return RiskLevel.MEDIUM
        elif volatility <= self.VOLATILITY_HIGH:
            return RiskLevel.HIGH
        else:
            return RiskLevel.VERY_HIGH
    
    def _get_recovery_config(self) -> Dict[str, Any]:
        """
        Return config untuk Hybrid Recovery system.
        
        Hybrid = Martingale ketika losing streak, Anti-Martingale ketika winning
        
        Returns:
            Dictionary dengan recovery configuration
        """
        risk_level = self._determine_risk_level()
        
        base_multiplier = 1.0
        max_level = 5
        recovery_mode = RecoveryMode.HYBRID
        
        if risk_level == RiskLevel.LOW:
            base_multiplier = 2.0
            max_level = 5
        elif risk_level == RiskLevel.MEDIUM:
            base_multiplier = 1.8
            max_level = 4
        elif risk_level == RiskLevel.HIGH:
            base_multiplier = 1.5
            max_level = 3
        else:
            base_multiplier = 1.3
            max_level = 2
        
        if self.consecutive_losses >= 2:
            recovery_mode = RecoveryMode.MARTINGALE
            current_multiplier = base_multiplier ** min(self.consecutive_losses, max_level)
        elif self.consecutive_wins >= 2:
            recovery_mode = RecoveryMode.ANTI_MARTINGALE
            current_multiplier = 1.0 + (self.consecutive_wins * 0.2)
        else:
            recovery_mode = RecoveryMode.HYBRID
            current_multiplier = 1.0
        
        return {
            'mode': recovery_mode,
            'base_multiplier': base_multiplier,
            'current_multiplier': current_multiplier,
            'max_level': max_level,
            'consecutive_wins': self.consecutive_wins,
            'consecutive_losses': self.consecutive_losses,
            'risk_level': risk_level
        }
    
    def analyze(self) -> Optional[TerminalAnalysisResult]:
        """
        Perform full Terminal Strategy analysis.
        
        Returns:
            TerminalAnalysisResult dengan signal dan probability
        """
        if self.total_ticks < self.MIN_TICKS_REQUIRED:
            return None
        
        probability_scores = self._calculate_probability()
        risk_level = self._determine_risk_level()
        recovery_config = self._get_recovery_config()
        volatility = self._calculate_volatility()
        
        total_probability = probability_scores['total']
        direction_str = probability_scores['direction']
        
        signal = None
        
        if total_probability >= self.MIN_CONFIDENCE and direction_str != 'WAIT':
            direction = SignalDirection.CALL if direction_str == 'CALL' else SignalDirection.PUT
            
            reasons = []
            if probability_scores['rsi'] >= 0.5:
                reasons.append(f"RSI signal ({probability_scores['rsi']:.1%})")
            if probability_scores['ema'] >= 0.5:
                reasons.append(f"EMA crossover ({probability_scores['ema']:.1%})")
            if probability_scores['macd'] >= 0.5:
                reasons.append(f"MACD momentum ({probability_scores['macd']:.1%})")
            if probability_scores['stoch'] >= 0.5:
                reasons.append(f"Stoch signal ({probability_scores['stoch']:.1%})")
            if probability_scores['adx'] >= 0.5:
                reasons.append(f"ADX trend ({probability_scores['adx']:.1%})")
            
            reason = "Smart Analysis: " + ", ".join(reasons) if reasons else "Multi-indicator confluence"
            
            signal = TerminalSignal(
                direction=direction,
                confidence=total_probability,
                risk_level=risk_level,
                recovery_mode=recovery_config['mode'],
                reason=reason
            )
        
        risk_band = f"{risk_level.value} (Volatility: {volatility:.4%})"
        
        indicators_used = {
            'RSI': probability_scores['rsi'],
            'EMA': probability_scores['ema'],
            'MACD': probability_scores['macd'],
            'Stochastic': probability_scores['stoch'],
            'ADX': probability_scores['adx']
        }
        
        return TerminalAnalysisResult(
            signal=signal,
            probability=total_probability,
            indicators_used=indicators_used,
            risk_band=risk_band,
            rsi_score=probability_scores['rsi'],
            ema_score=probability_scores['ema'],
            macd_score=probability_scores['macd'],
            stoch_score=probability_scores['stoch'],
            adx_score=probability_scores['adx'],
            volatility=volatility,
            tick_count=self.total_ticks
        )
    
    def get_signal_for_trading(self) -> Optional[TerminalSignal]:
        """
        Return signal jika confidence >= 0.80 (80%).
        
        Returns:
            TerminalSignal jika valid, None jika tidak
        """
        result = self.analyze()
        
        if result is None:
            return None
        
        if result.signal is not None and result.probability >= self.MIN_CONFIDENCE:
            return result.signal
        
        return None
    
    def update_trade_result(self, is_win: bool) -> None:
        """
        Update consecutive win/loss tracking untuk recovery system.
        
        Args:
            is_win: True jika trade menang, False jika kalah
        """
        if is_win:
            self.consecutive_wins += 1
            self.consecutive_losses = 0
        else:
            self.consecutive_losses += 1
            self.consecutive_wins = 0
    
    def reset_streaks(self) -> None:
        """Reset win/loss streaks"""
        self.consecutive_wins = 0
        self.consecutive_losses = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current strategy statistics"""
        volatility = self._calculate_volatility()
        risk_level = self._determine_risk_level()
        recovery_config = self._get_recovery_config()
        
        rsi = self._calculate_rsi() if self.total_ticks >= self.RSI_PERIOD else 50.0
        stoch_k, stoch_d = self._calculate_stochastic()
        adx, plus_di, minus_di = self._calculate_adx()
        
        return {
            'tick_count': self.total_ticks,
            'volatility': volatility,
            'risk_level': risk_level.value,
            'recovery_mode': recovery_config['mode'].value,
            'current_multiplier': recovery_config['current_multiplier'],
            'consecutive_wins': self.consecutive_wins,
            'consecutive_losses': self.consecutive_losses,
            'rsi': rsi,
            'stoch_k': stoch_k,
            'stoch_d': stoch_d,
            'adx': adx,
            'plus_di': plus_di,
            'minus_di': minus_di,
            'ready': self.total_ticks >= self.MIN_TICKS_REQUIRED
        }
    
    def clear_history(self) -> None:
        """Reset semua history dan caches"""
        self.tick_history.clear()
        self.high_history.clear()
        self.low_history.clear()
        self._rsi_gains.clear()
        self._rsi_losses.clear()
        self.total_ticks = 0
        self._last_price = 0.0
        
        self._ema_fast_cache = None
        self._ema_slow_cache = None
        self._macd_ema_fast_cache = None
        self._macd_ema_slow_cache = None
        self._macd_signal_cache = None
        
        self.consecutive_wins = 0
        self.consecutive_losses = 0
        
        logger.info("🖥️ Terminal Strategy history cleared")
