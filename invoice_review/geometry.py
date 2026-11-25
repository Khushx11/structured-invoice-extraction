"""Page-relative evidence coordinates in top-left origin."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Word:
    text: str
    box: tuple
    confidence: float = 1.0


def union(words):
    boxes = [word.box for word in words]
    return [min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes)]


def visual_rows(words):
    """Group words on the same visual baseline across table columns."""
    rows = []
    for word in sorted(words, key=lambda w: (w.box[1] + w.box[3], w.box[0])):
        y = (word.box[1] + word.box[3]) / 2
        if rows and abs(y - rows[-1][0]) <= max(.004, (word.box[3] - word.box[1]) * .40):
            rows[-1][1].append(word)
        else:
            rows.append((y, [word]))
    return [sorted(row, key=lambda w: w.box[0]) for _, row in rows]


def field(words=(), page=None, value=None):
    return {
        "value": value,
        "raw": " ".join(word.text for word in words) if words else None,
        "evidence": {"page": page, "box": union(words),
                     "ocr_confidence": round(min(w.confidence for w in words), 4)}
        if words else None,
    }

