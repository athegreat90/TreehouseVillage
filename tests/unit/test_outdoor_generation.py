from treehouse_village.buildings import OUTDOOR_DESIGNS, generate_outdoor, validate_building


def test_all_outdoor_designs_generate_valid_contracts():
    for outdoor_id in OUTDOOR_DESIGNS:
        assembly = generate_outdoor(outdoor_id)
        assert validate_building(assembly.scene, assembly.spec) == ()


def test_outdoor_fixtures_nonempty():
    for outdoor_id in OUTDOOR_DESIGNS:
        assembly = generate_outdoor(outdoor_id)
        assert assembly.spec.fixtures


def test_outdoor_deterministic():
    first = generate_outdoor("watchtower", seed=3)
    second = generate_outdoor("watchtower", seed=3)
    assert first.scene == second.scene
