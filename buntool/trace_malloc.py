import tracemalloc
from logging import Logger


class TraceMalloc:
    logger: Logger

    def __init__(self, logger: Logger) -> None:
        self.logger = logger
        tracemalloc.start()  # Start tracing memory allocations

    def log(self, n: int = 10):
        snapshot = tracemalloc.take_snapshot()
        top_stats = snapshot.statistics("lineno")

        # Display the top n memory-consuming lines
        for stat in top_stats[:n]:
            self.logger.debug(stat)
