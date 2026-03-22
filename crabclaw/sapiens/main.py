"""
Entry point for running a standalone AgentSapiens instance.

This script is for testing and demonstrating the functionality of the HAOS core
independent of the main crabclaw application.
"""
import threading
import time

from ..utils.logging_config import setup_logging
from .agent import AgentSapiens


def main():
    """
    Initializes and runs the AgentSapiens.
    """
    # Set up logging with INFO level (only when running standalone)
    setup_logging(level="INFO")
    print("Initializing AgentSapiens...")
    # Define the agent's innate personality drives (Six Desires)
    personality = {
        "connection": 0.8,    # Strong desire for social interaction
        "presentation": 0.3,  # Moderate desire to be seen
        "power": 0.5,         # Moderate desire for control
        "expression": 0.9,    # Very strong desire to express thoughts
        "data_quality": 0.6,  # Desire for high-quality information
        "signal_clarity": 0.4 # Desire for clear communication
    }

    agent = AgentSapiens(agent_id="sapiens-001", personality_drives=personality)

    # Run the agent's life loop in a separate thread
    life_thread = threading.Thread(target=agent.live, daemon=True)
    life_thread.start()

    # Keep the main thread alive to observe the agent
    # In a real application, this would be managed by the main app server
    try:
        while agent.is_alive:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutdown signal received.")
        agent.shutdown()

    life_thread.join(timeout=5.0)
    print("Main thread exiting.")

if __name__ == "__main__":
    main()
