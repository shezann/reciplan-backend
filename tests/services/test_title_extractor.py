import pytest
from services.title_extractor import TitleExtractor

def test_normalize_title_removes_hashtags_keeps_emojis():
    raw = "🍕 #foodie This is a #test title! 😋"
    norm = TitleExtractor.normalize_title(raw)
    assert "#" not in norm
    assert "🍕" in norm and "😋" in norm  # Emojis are preserved
    assert "This is a  title!" in norm  # Note: double space after "is a"
    # No forced capitalization - preserve original casing
    assert "this is a" in norm.lower()  # Check if the text is in the normalized string

def test_normalize_title_trims_whitespace():
    raw = "   this is a title that is way too long and should not be capped anymore, with extra words at the end.   "
    norm = TitleExtractor.normalize_title(raw)
    assert len(norm) > 80  # No character limit anymore
    assert norm.startswith("this is a")  # Trimmed whitespace
    assert norm.endswith("end.")  # Trimmed whitespace
    # No forced capitalization - preserve original casing

def test_from_metadata_prefers_nonempty():
    assert TitleExtractor.from_metadata("  My Title  ") == "My Title"
    assert TitleExtractor.from_metadata("") is None
    assert TitleExtractor.from_metadata(None) is None

def test_from_transcript_first_sentence():
    transcript = "First sentence. Second sentence! Third?"
    assert TitleExtractor.from_transcript(transcript) == "First sentence"
    transcript = "   .  !  ?  Only this remains"
    assert TitleExtractor.from_transcript(transcript) == "Only this remains"
    assert TitleExtractor.from_transcript("") is None 