from modules.swarm_ui.module.command_node import NodeType, Node

# Node
def test_node_init():
    parent = Node("parent")
    node = Node("root", node_type=NodeType.ROOT, parent=parent, parameter_list=["x", "y"], command_info="This is a test.")
    assert node.name == "ROOT"
    assert node.type == NodeType.ROOT
    assert node.parent == parent
    assert node.parameter_list == ["x", "y"]
    assert node.command_info == "This is a test."

    first_node = Node("root")
    second_node = Node("root")
    first_node.parameter_list.append("x")
    assert second_node.parameter_list == []

def test_node_get_branch_names():
    root_node = Node("ROOT")
    first_root_child = Node("FIRST_ROOT_CHILD", parent=root_node)
    second_root_child = Node("SECOND_ROOT_CHILD", parent=root_node)
    child_of_first_root_child = Node("CHILD_OF_FIRST_ROOT_CHILD", parent=first_root_child)

    assert root_node.get_branch_names() == ["ROOT"]
    assert second_root_child.get_branch_names() == ["ROOT", "SECOND_ROOT_CHILD"]
    assert child_of_first_root_child.get_branch_names() == ["ROOT", "FIRST_ROOT_CHILD", "CHILD_OF_FIRST_ROOT_CHILD"]

def test_node_set_parent():
    root_node = Node("ROOT")
    new_root_node = Node("NEW_ROOT")
    child_node = Node("CHILD", parent=root_node)

    child_node.set_parent(new_root_node)
    assert child_node.parent == new_root_node
