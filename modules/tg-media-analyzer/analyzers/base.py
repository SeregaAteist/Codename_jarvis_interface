from abc import ABC, abstractmethod
from pathlib import Path


class BaseAnalyzer(ABC):
    @abstractmethod
    async def analyze(
        self,
        image_paths: list[Path],
        transcripts: list[str],
        context: str = "",
    ) -> str:
        pass

    @abstractmethod
    def is_available(self) -> bool:
        pass
