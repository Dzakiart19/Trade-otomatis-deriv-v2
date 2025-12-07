"""
=============================================================
HYBRID MONEY MANAGER - Progressive + Deficit Recovery System
=============================================================
Modul ini mengimplementasikan sistem money management hybrid
yang menggabungkan Progressive Recovery dengan Deficit Tracking.

Lebih aman dari Martingale murni karena:
1. Progressive multiplier yang lebih konservatif
2. Deficit tracking untuk recovery bertahap
3. Risk level adaptif berdasarkan kondisi
4. Hard limits untuk proteksi modal

Cocok untuk:
- Modal kecil ($10+)
- Risk management yang lebih ketat
- Recovery yang sustainable

Risk Levels:
- LOW: 1.5x multiplier (konservatif)
- MEDIUM: 1.8x multiplier (balanced)
- HIGH: 2.1x multiplier (agresif)
- VERY HIGH: 2.5x multiplier (sangat agresif - tidak disarankan untuk modal kecil)
=============================================================
"""

from typing import Optional, Tuple, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import logging
import math

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Risk level untuk money management"""
    LOW = "LOW"           # 1.5x multiplier
    MEDIUM = "MEDIUM"     # 1.8x multiplier
    HIGH = "HIGH"         # 2.1x multiplier
    VERY_HIGH = "VERY_HIGH"  # 2.5x multiplier


@dataclass
class RecoveryState:
    """State untuk recovery tracking"""
    is_recovering: bool = False
    recovery_level: int = 0
    total_deficit: float = 0.0
    target_recovery: float = 0.0
    recovery_progress: float = 0.0
    consecutive_losses: int = 0
    consecutive_wins: int = 0
    

@dataclass
class StakeCalculation:
    """Hasil kalkulasi stake"""
    stake: float
    risk_level: RiskLevel
    is_recovery_stake: bool
    recovery_level: int
    reason: str
    estimated_profit: float
    max_loss_if_fail: float


@dataclass
class SessionMetrics:
    """Metrics untuk session trading"""
    starting_balance: float = 0.0
    current_balance: float = 0.0
    peak_balance: float = 0.0
    lowest_balance: float = 0.0
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    total_profit: float = 0.0
    max_drawdown: float = 0.0
    recovery_attempts: int = 0
    successful_recoveries: int = 0
    failed_recoveries: int = 0


class HybridMoneyManager:
    """
    Hybrid Money Management System
    
    Menggabungkan:
    1. Progressive stake increase (lebih halus dari Martingale)
    2. Deficit recovery tracking
    3. Risk-based multipliers
    4. Capital protection limits
    """
    
    # Risk multipliers
    MULTIPLIERS = {
        RiskLevel.LOW: 1.5,
        RiskLevel.MEDIUM: 1.8,
        RiskLevel.HIGH: 2.1,
        RiskLevel.VERY_HIGH: 2.5
    }
    
    # Maximum recovery levels per risk
    MAX_RECOVERY_LEVELS = {
        RiskLevel.LOW: 6,
        RiskLevel.MEDIUM: 5,
        RiskLevel.HIGH: 4,
        RiskLevel.VERY_HIGH: 3
    }
    
    # Default configuration
    DEFAULT_MIN_STAKE = 0.35
    DEFAULT_MAX_STAKE_PCT = 0.20  # Max 20% of balance per trade
    DEFAULT_DAILY_LOSS_LIMIT = 0.30  # 30% of starting balance
    DEFAULT_PROFIT_TARGET = 0.10  # 10% daily target
    
    def __init__(
        self,
        starting_balance: float,
        base_stake: float = 0.35,
        risk_level: RiskLevel = RiskLevel.MEDIUM,
        min_stake: float = 0.35,
        max_stake_pct: float = 0.20,
        daily_loss_limit: float = 0.30,
        profit_target: float = 0.10
    ):
        """
        Initialize Hybrid Money Manager.
        
        Args:
            starting_balance: Balance awal
            base_stake: Stake dasar untuk trading normal
            risk_level: Risk level yang dipilih
            min_stake: Minimum stake (biasanya $0.35)
            max_stake_pct: Maximum stake sebagai persentase balance
            daily_loss_limit: Batas loss harian (persentase dari balance awal)
            profit_target: Target profit harian (persentase dari balance awal)
        """
        self.starting_balance = starting_balance
        self.current_balance = starting_balance
        self.base_stake = max(base_stake, min_stake)
        self.risk_level = risk_level
        self.min_stake = min_stake
        self.max_stake_pct = max_stake_pct
        self.daily_loss_limit = daily_loss_limit
        self.profit_target = profit_target
        
        # State tracking
        self.recovery_state = RecoveryState()
        self.metrics = SessionMetrics(
            starting_balance=starting_balance,
            current_balance=starting_balance,
            peak_balance=starting_balance,
            lowest_balance=starting_balance
        )
        
        # History
        self.trade_history: List[Dict[str, Any]] = []
        self.stake_history: List[float] = []
        
        # Calculate limits
        self._update_limits()
        
        logger.info(
            f"💰 Hybrid Money Manager initialized\n"
            f"   Balance: ${starting_balance:.2f}\n"
            f"   Base stake: ${self.base_stake:.2f}\n"
            f"   Risk level: {risk_level.value}\n"
            f"   Max recovery levels: {self.max_recovery_levels}"
        )
    
    def _update_limits(self) -> None:
        """Update calculated limits"""
        self.max_stake = max(
            self.min_stake,
            self.current_balance * self.max_stake_pct
        )
        self.max_recovery_levels = self.MAX_RECOVERY_LEVELS[self.risk_level]
        self.multiplier = self.MULTIPLIERS[self.risk_level]
        
        # Daily limits
        self.daily_loss_amount = self.starting_balance * self.daily_loss_limit
        self.profit_target_amount = self.starting_balance * self.profit_target
    
    def calculate_stake(self) -> StakeCalculation:
        """
        Calculate next stake berdasarkan current state.
        
        Returns:
            StakeCalculation dengan stake yang direkomendasikan
        """
        self._update_limits()
        
        # Check if in recovery mode
        if self.recovery_state.is_recovering:
            return self._calculate_recovery_stake()
        else:
            return self._calculate_normal_stake()
    
    def _calculate_normal_stake(self) -> StakeCalculation:
        """Calculate stake untuk trading normal (tidak dalam recovery)"""
        stake = self.base_stake
        reason = "Normal trading stake"
        
        # Adjust based on consecutive wins (progressive increase)
        if self.recovery_state.consecutive_wins >= 3:
            bonus_multiplier = 1.0 + (self.recovery_state.consecutive_wins - 2) * 0.1
            bonus_multiplier = min(bonus_multiplier, 1.5)  # Max 50% increase
            stake = self.base_stake * bonus_multiplier
            reason = f"Winning streak bonus ({self.recovery_state.consecutive_wins} wins)"
        
        # Apply limits
        stake = max(self.min_stake, min(stake, self.max_stake))
        
        # Calculate estimated profit (assuming ~95% payout)
        estimated_profit = stake * 0.95
        
        return StakeCalculation(
            stake=round(stake, 2),
            risk_level=self.risk_level,
            is_recovery_stake=False,
            recovery_level=0,
            reason=reason,
            estimated_profit=estimated_profit,
            max_loss_if_fail=stake
        )
    
    def _calculate_recovery_stake(self) -> StakeCalculation:
        """Calculate stake untuk recovery mode"""
        level = self.recovery_state.recovery_level
        
        # Progressive recovery calculation
        # Level 1: base * multiplier
        # Level 2: base * multiplier^1.5
        # Level 3: base * multiplier^2
        # etc.
        
        if level == 0:
            stake = self.base_stake * self.multiplier
        else:
            # Use softer exponential growth
            exponent = 1 + (level * 0.5)  # 1, 1.5, 2, 2.5, 3...
            stake = self.base_stake * (self.multiplier ** exponent)
        
        # Apply limits
        stake = max(self.min_stake, min(stake, self.max_stake))
        
        # Check if stake is enough to recover deficit
        estimated_profit = stake * 0.95
        deficit = self.recovery_state.total_deficit
        
        if estimated_profit >= deficit:
            reason = f"Recovery L{level}: Full recovery possible (${estimated_profit:.2f} >= ${deficit:.2f})"
        else:
            remaining = deficit - estimated_profit
            reason = f"Recovery L{level}: Partial recovery (${remaining:.2f} remaining)"
        
        return StakeCalculation(
            stake=round(stake, 2),
            risk_level=self.risk_level,
            is_recovery_stake=True,
            recovery_level=level,
            reason=reason,
            estimated_profit=estimated_profit,
            max_loss_if_fail=stake + self.recovery_state.total_deficit
        )
    
    def record_trade(self, stake: float, profit: float, is_win: bool) -> Dict[str, Any]:
        """
        Record hasil trade dan update state.
        
        Args:
            stake: Stake yang digunakan
            profit: Profit/loss dari trade
            is_win: True jika menang
            
        Returns:
            Dictionary dengan updated state info
        """
        # Update balance
        old_balance = self.current_balance
        self.current_balance += profit
        
        # Update metrics
        self.metrics.current_balance = self.current_balance
        self.metrics.total_trades += 1
        self.metrics.total_profit += profit
        
        if is_win:
            self.metrics.wins += 1
        else:
            self.metrics.losses += 1
        
        # Update peak/lowest
        if self.current_balance > self.metrics.peak_balance:
            self.metrics.peak_balance = self.current_balance
        if self.current_balance < self.metrics.lowest_balance:
            self.metrics.lowest_balance = self.current_balance
        
        # Calculate drawdown
        current_drawdown = self.metrics.peak_balance - self.current_balance
        if current_drawdown > self.metrics.max_drawdown:
            self.metrics.max_drawdown = current_drawdown
        
        # Update recovery state
        if is_win:
            self._handle_win(stake, profit)
        else:
            self._handle_loss(stake)
        
        # Record history
        trade_record = {
            'timestamp': datetime.now().isoformat(),
            'stake': stake,
            'profit': profit,
            'is_win': is_win,
            'balance_before': old_balance,
            'balance_after': self.current_balance,
            'recovery_level': self.recovery_state.recovery_level,
            'is_recovery': self.recovery_state.is_recovering
        }
        self.trade_history.append(trade_record)
        self.stake_history.append(stake)
        
        # Update limits
        self._update_limits()
        
        return {
            'balance': self.current_balance,
            'profit': profit,
            'is_win': is_win,
            'in_recovery': self.recovery_state.is_recovering,
            'recovery_level': self.recovery_state.recovery_level,
            'deficit': self.recovery_state.total_deficit,
            'should_stop': self._should_stop_trading()
        }
    
    def _handle_win(self, stake: float, profit: float) -> None:
        """Handle win result"""
        self.recovery_state.consecutive_wins += 1
        self.recovery_state.consecutive_losses = 0
        
        if self.recovery_state.is_recovering:
            # Check if fully recovered
            self.recovery_state.total_deficit -= profit
            self.recovery_state.recovery_progress = profit
            
            if self.recovery_state.total_deficit <= 0:
                # Full recovery achieved
                logger.info(
                    f"✅ Recovery COMPLETE! "
                    f"Recovered from ${abs(self.recovery_state.total_deficit + profit):.2f} deficit"
                )
                self.metrics.successful_recoveries += 1
                self._reset_recovery_state()
            else:
                logger.info(
                    f"📈 Partial recovery: ${profit:.2f} recovered, "
                    f"${self.recovery_state.total_deficit:.2f} remaining"
                )
    
    def _handle_loss(self, stake: float) -> None:
        """Handle loss result"""
        self.recovery_state.consecutive_losses += 1
        self.recovery_state.consecutive_wins = 0
        
        if not self.recovery_state.is_recovering:
            # Start recovery mode
            self.recovery_state.is_recovering = True
            self.recovery_state.recovery_level = 0
            self.recovery_state.total_deficit = stake
            self.recovery_state.target_recovery = stake
            self.metrics.recovery_attempts += 1
            
            logger.info(f"🔄 Entering recovery mode: ${stake:.2f} to recover")
        else:
            # Already in recovery, increase level
            self.recovery_state.recovery_level += 1
            self.recovery_state.total_deficit += stake
            
            if self.recovery_state.recovery_level >= self.max_recovery_levels:
                # Max recovery level reached - STOP
                logger.warning(
                    f"⛔ Max recovery level ({self.max_recovery_levels}) reached! "
                    f"Total deficit: ${self.recovery_state.total_deficit:.2f}"
                )
                self.metrics.failed_recoveries += 1
            else:
                logger.info(
                    f"📉 Recovery L{self.recovery_state.recovery_level}: "
                    f"Total deficit now ${self.recovery_state.total_deficit:.2f}"
                )
    
    def _reset_recovery_state(self) -> None:
        """Reset recovery state after successful recovery"""
        self.recovery_state = RecoveryState()
    
    def _should_stop_trading(self) -> bool:
        """Check if trading should be stopped"""
        # 1. Check daily loss limit
        daily_loss = self.starting_balance - self.current_balance
        if daily_loss >= self.daily_loss_amount:
            logger.warning(f"⛔ Daily loss limit reached: ${daily_loss:.2f}")
            return True
        
        # 2. Check max recovery level
        if (self.recovery_state.is_recovering and 
            self.recovery_state.recovery_level >= self.max_recovery_levels):
            return True
        
        # 3. Check minimum balance (keep at least 3x min stake)
        if self.current_balance < self.min_stake * 3:
            logger.warning(f"⛔ Balance too low: ${self.current_balance:.2f}")
            return True
        
        return False
    
    def should_take_profit(self) -> bool:
        """Check if profit target reached"""
        current_profit = self.current_balance - self.starting_balance
        if current_profit >= self.profit_target_amount:
            logger.info(
                f"🎯 Profit target reached! "
                f"${current_profit:.2f} / ${self.profit_target_amount:.2f}"
            )
            return True
        return False
    
    def get_state_summary(self) -> str:
        """Get human-readable state summary"""
        current_profit = self.current_balance - self.starting_balance
        profit_pct = (current_profit / self.starting_balance * 100) if self.starting_balance > 0 else 0
        win_rate = (self.metrics.wins / self.metrics.total_trades * 100) if self.metrics.total_trades > 0 else 0
        
        lines = [
            f"💰 Balance: ${self.current_balance:.2f} ({profit_pct:+.1f}%)",
            f"📊 Trades: {self.metrics.total_trades} (W: {self.metrics.wins} / L: {self.metrics.losses})",
            f"📈 Win Rate: {win_rate:.1f}%",
            f"⚡ Risk Level: {self.risk_level.value}",
        ]
        
        if self.recovery_state.is_recovering:
            lines.append(
                f"🔄 Recovery L{self.recovery_state.recovery_level}: "
                f"${self.recovery_state.total_deficit:.2f} to recover"
            )
        
        if self.metrics.max_drawdown > 0:
            lines.append(f"📉 Max Drawdown: ${self.metrics.max_drawdown:.2f}")
        
        return "\n".join(lines)
    
    def update_balance(self, new_balance: float) -> None:
        """Update current balance (dari external source)"""
        self.current_balance = new_balance
        self.metrics.current_balance = new_balance
        self._update_limits()
    
    def set_risk_level(self, risk_level: RiskLevel) -> None:
        """Change risk level"""
        old_level = self.risk_level
        self.risk_level = risk_level
        self._update_limits()
        logger.info(f"⚡ Risk level changed: {old_level.value} -> {risk_level.value}")
    
    def get_next_stake_preview(self, levels: int = 5) -> List[Dict[str, float]]:
        """
        Preview next N stake levels untuk planning.
        
        Returns:
            List of dicts dengan stake dan cumulative loss untuk setiap level
        """
        preview = []
        cumulative = 0.0
        
        for level in range(levels):
            if level == 0:
                stake = self.base_stake * self.multiplier
            else:
                exponent = 1 + (level * 0.5)
                stake = self.base_stake * (self.multiplier ** exponent)
            
            stake = min(stake, self.max_stake)
            cumulative += stake
            
            preview.append({
                'level': level + 1,
                'stake': round(stake, 2),
                'cumulative_risk': round(cumulative, 2),
                'can_afford': cumulative <= self.current_balance * 0.8  # Keep 20% buffer
            })
        
        return preview
    
    def reset_session(self, new_balance: Optional[float] = None) -> None:
        """Reset session untuk hari baru"""
        balance = new_balance if new_balance is not None else self.current_balance
        
        self.starting_balance = balance
        self.current_balance = balance
        self.recovery_state = RecoveryState()
        self.metrics = SessionMetrics(
            starting_balance=balance,
            current_balance=balance,
            peak_balance=balance,
            lowest_balance=balance
        )
        self.trade_history.clear()
        self.stake_history.clear()
        self._update_limits()
        
        logger.info(f"🔄 Session reset with balance: ${balance:.2f}")


def create_small_capital_manager(balance: float, stake: float = 0.35) -> HybridMoneyManager:
    """
    Factory function untuk membuat money manager yang dioptimalkan untuk modal kecil.
    
    Args:
        balance: Balance saat ini
        stake: Base stake (default $0.35)
    
    Returns:
        Configured HybridMoneyManager
    """
    # Untuk modal kecil, gunakan setting konservatif
    if balance <= 10:
        risk_level = RiskLevel.LOW
        max_stake_pct = 0.15  # Max 15% per trade
        daily_loss_limit = 0.25  # Max 25% daily loss
        profit_target = 0.10  # 10% daily target
    elif balance <= 25:
        risk_level = RiskLevel.MEDIUM
        max_stake_pct = 0.18
        daily_loss_limit = 0.30
        profit_target = 0.12
    elif balance <= 50:
        risk_level = RiskLevel.MEDIUM
        max_stake_pct = 0.20
        daily_loss_limit = 0.30
        profit_target = 0.15
    else:
        risk_level = RiskLevel.HIGH
        max_stake_pct = 0.20
        daily_loss_limit = 0.35
        profit_target = 0.20
    
    return HybridMoneyManager(
        starting_balance=balance,
        base_stake=stake,
        risk_level=risk_level,
        min_stake=0.35,
        max_stake_pct=max_stake_pct,
        daily_loss_limit=daily_loss_limit,
        profit_target=profit_target
    )
