from pathlib import Path

from src.preprocessing.pipeline import _save_split


class EmptySplit:
    def __len__(self):
        return 0


def test_saved_split_metadata_uses_relative_portable_path(tmp_path: Path):
    info = _save_split("train", EmptySplit(), tmp_path)

    assert info["path"] == "train.npz"
    assert (tmp_path / info["path"]).is_file()
