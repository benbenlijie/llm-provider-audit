import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from model_checker.utils.dotenv import load_default_env, load_env_file


class DotenvTests(unittest.TestCase):
    def test_load_env_file_parses_basic_values(self) -> None:
        with TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "# comment",
                        "PLAIN=value",
                        'QUOTED="hello world"',
                        "export TOKEN=abc123",
                    ]
                ),
                encoding="utf-8",
            )
            with patch.dict(os.environ, {}, clear=True):
                loaded = load_env_file(env_path)
                self.assertTrue(loaded)
                self.assertEqual(os.environ["PLAIN"], "value")
                self.assertEqual(os.environ["QUOTED"], "hello world")
                self.assertEqual(os.environ["TOKEN"], "abc123")

    def test_load_env_file_does_not_override_existing_values(self) -> None:
        with TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text("PLAIN=new-value\n", encoding="utf-8")
            with patch.dict(os.environ, {"PLAIN": "existing-value"}, clear=True):
                load_env_file(env_path)
                self.assertEqual(os.environ["PLAIN"], "existing-value")

    def test_load_default_env_searches_parent_directories(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            nested = root / "a" / "b"
            nested.mkdir(parents=True)
            (root / ".env").write_text("PARENT_VALUE=loaded\n", encoding="utf-8")
            with patch.dict(os.environ, {}, clear=True):
                loaded_path = load_default_env(start_dir=nested)
                self.assertEqual(loaded_path, root / ".env")
                self.assertEqual(os.environ["PARENT_VALUE"], "loaded")


if __name__ == "__main__":
    unittest.main()
