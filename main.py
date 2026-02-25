#!/usr/bin/env python3
"""
Autonomous Algorithmic Breeder (AAB) - Main Entry Point
Self-evolving AI system for breeding algorithmic trading models
"""
import asyncio
import logging
import signal
import sys
from typing import Optional, Dict, Any

from aab_architecture.genetic_programming import StrategyBreeder
from aab_architecture.simulation import TradingSimulator
from aab_architecture.reinforcement import RL_Optimizer
from aab_architecture.deployment import StrategyDeployer
from aab_architecture.firebase_client import FirebaseManager
from aab_architecture.config import Config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('aab_system.log')
    ]
)
logger = logging.getLogger(__name__)

class AABSystem:
    """Main orchestrator for the Autonomous Algorithmic Breeder system"""
    
    def __init__(self):
        """Initialize the AAB system with all components"""
        logger.info("🚀 Initializing Autonomous Algorithmic Breeder System")
        
        # Load configuration
        self.config = Config()
        
        # Initialize Firebase for state management
        self.firebase = FirebaseManager()
        
        # Initialize system components
        self.breeder = StrategyBreeder(self.firebase)
        self.simulator = TradingSimulator(self.firebase)
        self.optimizer = RL_Optimizer(self.firebase)
        self.deployer = StrategyDeployer(self.firebase)
        
        # System state
        self.is_running = False
        self.generation_count = 0
        self.best_strategy_id: Optional[str] = None
        
        logger.info("✅ AAB System initialized successfully")
    
    async def initialize_system(self) -> bool:
        """Initialize all system components asynchronously"""
        try:
            logger.info("🔄 Initializing system components...")
            
            # Initialize Firebase connection
            if not await self.firebase.initialize():
                logger.error("❌ Firebase initialization failed")
                return False
            
            # Load initial population if exists
            await self.breeder.load_initial_population()
            
            logger.info("✅ System initialization complete")
            return True
            
        except Exception as e:
            logger.error(f"❌ System initialization failed: {e}", exc_info=True)
            return False
    
    async def run_evolution_cycle(self) -> Dict[str, Any]:
        """Execute one complete evolution cycle"""
        try:
            self.generation_count += 1
            logger.info(f"🔄 Starting evolution cycle {self.generation_count}")
            
            # 1. Breed new strategies
            strategies = await self.breeder.breed_new_generation()
            if not strategies:
                logger.warning("⚠️ No strategies generated in breeding phase")
                return {"success": False, "error": "No strategies generated"}
            
            # 2. Simulate and evaluate strategies
            simulation_results = []
            for strategy in strategies:
                result = await self.simulator.simulate_strategy(strategy)
                if result:
                    simulation_results.append(result)
            
            if not simulation_results:
                logger.warning("⚠️ No simulation results generated")
                return {"success": False, "error": "No simulation results"}
            
            # 3. Optimize with reinforcement learning
            optimized_strategy = await self.optimizer.optimize_strategy(simulation_results)
            
            if optimized_strategy:
                # 4. Deploy if meets criteria
                deployment_result = await self.deployer.evaluate_for_deployment(
                    optimized_strategy, 
                    simulation_results
                )
                
                # 5. Update Firebase with results
                await self.firebase.update_evolution_state({
                    "generation": self.generation_count,
                    "strategies_evaluated": len(strategies),
                    "best_sharpe_ratio": max(r.get("sharpe_ratio", 0) for r in simulation_results),
                    "timestamp": self.firebase.get_timestamp()
                })
                
                logger.info(f"✅ Evolution cycle {self.generation_count} completed successfully")
                return {
                    "success": True,
                    "generation": self.generation_count,
                    "strategies_evaluated": len(strategies),
                    "deployment_triggered": deployment_result.get("deployed", False)
                }
            
            return {"success": False, "error": "Optimization failed"}
            
        except Exception as e:
            logger.error(f"❌ Evolution cycle failed: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    async def run_continuous(self) -> None:
        """Run the AAB system continuously until stopped"""
        self.is_running = True
        
        # Setup graceful shutdown
        def signal_handler(signum, frame):
            logger.info("🛑 Received shutdown signal")
            self.is_running = False
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        logger.info("🏁 Starting continuous evolution mode")
        
        while self.is_running:
            try:
                result = await self.run_evolution_cycle()
                
                if not result.get("success", False):
                    logger.warning(f"⚠️ Evolution cycle unsuccessful: {result.get('error')}")
                    # Implement exponential backoff on failures
                    await asyncio.sleep(self.config.get("cycle_retry_delay", 60))
                else:
                    # Wait for next cycle
                    cycle_interval = self.config.get("evolution_cycle_interval", 300)
                    logger.info(f"⏳ Waiting {cycle_interval} seconds for next cycle...")
                    await asyncio.sleep(cycle_interval)
                    
            except asyncio.CancelledError:
                logger.info("🛑 Evolution cycle cancelled")
                break
            except Exception as e:
                logger.error(f"💥 Critical error in main loop: {e}", exc_info=True)
                await asyncio.sleep(60)  # Wait before retry
        
        logger.info("👋 AAB System shutting down")
    
    async def cleanup(self) -> None:
        """Cleanup system resources"""
        try:
            logger.info("🧹 Cleaning up system resources...")
            await self.firebase.cleanup()
            logger.info("✅ Cleanup complete")
        except Exception as e:
            logger.error(f"❌ Cleanup failed: {e}")

async def main():
    """Main entry point"""
    aab_system = AABSystem()
    
    try:
        # Initialize system
        if not await aab_system.initialize_system():
            logger.error("Failed to initialize AAB system")
            sys.exit(1)
        
        # Run continuous evolution
        await aab_system.run_continuous()
        
    except KeyboardInterrupt:
        logger.info("👋 Shutdown requested by user")
    except Exception as e:
        logger.error(f"💥 Fatal error in AAB system: {e}", exc_info=True)
        sys.exit(1)
    finally:
        await aab_system.cleanup()

if __name__ == "__main__":
    asyncio.run(main())