from utils.choices import ChoiceSet, spellings

containers = ChoiceSet({"Audio": "mp3", "Video": "mp4"})
encoders = ChoiceSet({"Base64": "b64", "Caesar Cipher": "caesar"})
indents = ChoiceSet({"2 spaces": "2", "Tab": "tab"})


def test_spellings_cover_the_value_and_the_label() -> None:
    assert spellings("Audio", "mp3") == {"audio", "mp3"}


def test_spellings_cover_punctuated_forms_of_a_two_word_label() -> None:
    assert spellings("Caesar Cipher", "caesar") == {
        "caesar",
        "caesar cipher",
        "caesarcipher",
        "caesar-cipher",
        "caesar_cipher",
    }


def test_the_slash_menu_only_ever_sees_labels_and_values() -> None:
    assert [(c.name, c.value) for c in containers.options] == [
        ("Audio", "mp3"),
        ("Video", "mp4"),
    ]


def test_resolve_falls_back_to_the_default_for_nothing_supplied() -> None:
    assert containers.resolve(None, "mp4") == "mp4"


def test_resolve_normalises_a_label_that_reached_it_unconverted() -> None:
    assert containers.resolve("Audio", "mp4") == "mp3"


def test_resolve_uses_the_default_rather_than_inventing_a_value() -> None:
    assert containers.resolve("nonsense", "mp4") == "mp4"


def test_a_label_whose_spelling_needs_quoting_still_resolves() -> None:
    assert indents.resolve("2 spaces", "2") == "2"
    assert indents.resolve("2spaces", "2") == "2"
