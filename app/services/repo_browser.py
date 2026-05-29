from app.models.schemas import RepoFilePayload, RepoTreeNode, RepoTreePayload


def build_repo_tree_payload(repo_data: dict, tree_data: dict) -> RepoTreePayload:
    root: dict[str, dict] = {}

    for item in tree_data.get("tree", []):
        item_type = item.get("type")
        if item_type not in {"tree", "blob"}:
            continue

        path = item["path"]
        parts = path.split("/")
        current = root
        current_path_parts: list[str] = []

        for index, part in enumerate(parts):
            current_path_parts.append(part)
            node_path = "/".join(current_path_parts)
            is_last = index == len(parts) - 1
            node_type = "file" if is_last and item_type == "blob" else "dir"

            if part not in current:
                current[part] = {
                    "name": part,
                    "path": node_path,
                    "type": node_type,
                    "children": {},
                }
            elif current[part]["type"] == "file" and node_type == "dir":
                current[part]["type"] = "dir"

            current = current[part]["children"]

    return RepoTreePayload(
        repoFullName=repo_data["full_name"],
        defaultBranch=repo_data["default_branch"],
        nodes=_dict_to_nodes(root),
    )


def _dict_to_nodes(node_map: dict[str, dict]) -> list[RepoTreeNode]:
    directories: list[RepoTreeNode] = []
    files: list[RepoTreeNode] = []

    for key in sorted(node_map.keys(), key=lambda item: (node_map[item]["type"] != "dir", item.lower())):
        raw = node_map[key]
        node = RepoTreeNode(
            name=raw["name"],
            path=raw["path"],
            type=raw["type"],
            children=_dict_to_nodes(raw["children"]) if raw["type"] == "dir" else [],
        )
        if node.type == "dir":
            directories.append(node)
        else:
            files.append(node)

    return directories + files


def build_repo_file_payload(repo_data: dict, file_data: dict) -> RepoFilePayload:
    decoded_content = file_data.get("decoded_content", "")
    truncated = file_data.get("truncated", False)
    return RepoFilePayload(
        repoFullName=repo_data["full_name"],
        path=file_data["path"],
        name=file_data["name"],
        size=file_data.get("size", 0),
        encoding=file_data.get("encoding") or "utf-8",
        content=decoded_content,
        truncated=truncated,
        htmlUrl=file_data.get("html_url"),
    )
