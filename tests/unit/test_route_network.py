"""T5: village route graph validated with 3D pathfinding over the scene."""

from treehouse_village.bridges import BridgeSpec, generate_bridge
from treehouse_village.geometry.model import Block, Scene, Vec3
from treehouse_village.routes import RouteGraph, validate_routes


def _platform(scene: Scene, center: Vec3, y: int) -> None:
    for dx in range(-2, 3):
        for dz in range(-2, 3):
            scene.set_block(Vec3(center.x + dx, y, center.z + dz),
                            Block("minecraft:jungle_planks"))


def _bridged_scene(*, sloped: bool = False) -> Scene:
    scene = Scene()
    end = Vec3(10, 8, 0) if sloped else Vec3(10, 5, 0)
    # Anchor decks sit outside the bridge footprint (start side x<=0, end
    # side x>=end.x) so the bridge railings never overlap the platforms.
    for dx in range(-2, 1):
        for dz in range(-2, 3):
            scene.set_block(Vec3(dx, 5, dz), Block("minecraft:jungle_planks"))
    for dx in range(0, 3):
        for dz in range(-2, 3):
            scene.set_block(end + Vec3(dx, 0, dz), Block("minecraft:jungle_planks"))
    assembly = generate_bridge(BridgeSpec(Vec3(0, 5, 0), end))
    for position, block in assembly.scene.blocks():
        scene.set_block(position, block)
    return scene


def _graph(*, sloped: bool = False) -> RouteGraph:
    far = Vec3(10, 9, 1) if sloped else Vec3(11, 6, 1)
    return RouteGraph(
        nodes=(
            ("entrance", Vec3(0, 6, 0)),
            ("village_hall", Vec3(1, 6, -1)),
            ("lookout", far),
        ),
        edges=(
            ("entrance", "village_hall"),
            ("entrance", "lookout"),
        ),
    )


def test_connected_village_has_no_route_issues():
    assert validate_routes(_bridged_scene(), _graph(), "entrance") == ()


def test_broken_bridge_reports_unreachable_destination():
    # Both anchor platforms exist but no bridge connects them.
    scene = Scene()
    _platform(scene, Vec3(0, 0, 0), 5)
    _platform(scene, Vec3(10, 0, 0), 5)
    issues = validate_routes(scene, _graph(), "entrance")
    assert [issue.node for issue in issues] == ["lookout"]
    assert issues[0].code == "unreachable_node"


def test_sloped_route_requires_climbing():
    scene = _bridged_scene(sloped=True)
    # Single-block climbing crosses the stepped bridge...
    assert validate_routes(scene, _graph(sloped=True), "entrance",
                           max_climb=1) == ()
    # ...and the default horizontal-only model honestly rejects the slope.
    issues = validate_routes(scene, _graph(sloped=True), "entrance")
    assert [issue.node for issue in issues] == ["lookout"]


def test_unknown_entrance_is_reported():
    issues = validate_routes(_bridged_scene(), _graph(), "citadel")
    assert [issue.code for issue in issues] == ["unknown_entrance"]


def test_edges_must_reference_known_nodes():
    graph = RouteGraph(nodes=(("entrance", Vec3(0, 6, 0)),),
                       edges=(("entrance", "nowhere"), ("ghost", "entrance")))
    codes = sorted(issue.code for issue in
                   validate_routes(_bridged_scene(), graph, "entrance"))
    assert codes == ["unknown_edge_node", "unknown_edge_node"]


def test_unwalkable_node_position_is_reported():
    graph = RouteGraph(nodes=(("entrance", Vec3(0, 6, 0)),
                              ("midair", Vec3(5, 20, 0))), edges=())
    issues = validate_routes(_bridged_scene(), graph, "entrance")
    assert [(issue.code, issue.node) for issue in issues] == \
        [("unwalkable_node", "midair")]


def test_duplicate_node_names_are_reported():
    graph = RouteGraph(nodes=(("entrance", Vec3(0, 6, 0)),
                              ("entrance", Vec3(1, 6, 0))), edges=())
    codes = [issue.code for issue in validate_routes(_bridged_scene(), graph,
                                                     "entrance")]
    assert codes == ["duplicate_node"]


def test_isolated_but_walkable_node_is_unreachable():
    scene = Scene()
    _platform(scene, Vec3(0, 0, 0), 5)
    _platform(scene, Vec3(30, 0, 0), 5)
    graph = RouteGraph(nodes=(("entrance", Vec3(0, 6, 0)),
                              ("island", Vec3(30, 6, 0))), edges=())
    issues = validate_routes(scene, graph, "entrance")
    assert [(issue.code, issue.node) for issue in issues] == \
        [("unreachable_node", "island")]
