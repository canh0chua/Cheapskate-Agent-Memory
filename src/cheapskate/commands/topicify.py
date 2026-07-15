"""
memory topicify command - Auto-group memories into topic files.

Groups related memories by tags, entities, or HRR vector similarity.
Creates/updates topic files under ~/.claude/projects/<project>/memory/topics/
Updates topics table in the database.
"""

import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from cheapskate.config import Config
from cheapskate.db import Database
from cheapskate.hrr import encode, similarity, unpack_vector


def get_claude_memory_dir(project: str) -> Path:
    """Get Claude Code compatible memory directory path."""
    home = Path.home()
    return home / ".claude" / "projects" / project / "memory"


def get_topics_dir(project: str) -> Path:
    """Get topics directory for a project."""
    return get_claude_memory_dir(project) / "topics"


def extract_keywords(text: str) -> set:
    """Extract meaningful keywords from text."""
    # Remove common stopwords
    stopwords = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "must", "shall", "can", "need", "dare",
        "to", "of", "in", "for", "on", "with", "at", "by", "from", "as",
        "into", "through", "during", "before", "after", "above", "below",
        "and", "but", "or", "nor", "so", "yet", "both", "either", "neither",
        "not", "only", "just", "also", "very", "too", "more", "most",
        "this", "that", "these", "those", "it", "its", "they", "them", "their",
        "we", "us", "our", "you", "your", "he", "she", "him", "her", "his",
        "i", "me", "my", "what", "which", "who", "whom", "when", "where",
        "why", "how", "all", "each", "every", "any", "some", "no", "such",
        "about", "using", "use", "used", "using", "here", "there", "then",
    }
    # Extract words (letters and numbers)
    words = re.findall(r"[a-zA-Z0-9]+", text.lower())
    # Filter out short words and stopwords
    return {
        w for w in words
        if len(w) > 2 and w not in stopwords
    }


def compute_memory_similarity(mem1: Dict[str, Any], mem2: Dict[str, Any]) -> float:
    """Compute semantic similarity between two memories using HRR vectors."""
    # If embeddings exist, compute vector similarity
    if mem1.get("embedding") and mem2.get("embedding"):
        try:
            v1 = unpack_vector(mem1["embedding"])
            v2 = unpack_vector(mem2["embedding"])
            return similarity(v1, v2)
        except Exception:
            pass

    # Fallback: keyword overlap
    kw1 = extract_keywords(mem1["content"])
    kw2 = extract_keywords(mem2["content"])

    if not kw1 or not kw2:
        return 0.0

    overlap = len(kw1 & kw2)
    union = len(kw1 | kw2)
    return overlap / union if union > 0 else 0.0


def group_memories_by_tags(memories: List[Dict[str, Any]]) -> Dict[str, List[Dict]]:
    """Group memories by their tags."""
    groups = defaultdict(list)
    for mem in memories:
        metadata = mem.get("metadata") or {}
        tags = metadata.get("tags", [])
        if tags:
            for tag in tags:
                groups[tag].append(mem)
        else:
            groups["untagged"].append(mem)
    return dict(groups)


def group_memories_by_similarity(
    memories: List[Dict[str, Any]],
    threshold: float = 0.3,
) -> List[List[Dict[str, Any]]]:
    """Group memories by semantic similarity using HRR vectors."""
    if not memories:
        return []

    groups = []
    assigned = set()

    for i, mem in enumerate(memories):
        if i in assigned:
            continue

        # Start a new group with this memory
        group = [mem]
        assigned.add(i)

        # Find similar memories
        for j, other in enumerate(memories[i + 1:], start=i + 1):
            if j in assigned:
                continue

            sim = compute_memory_similarity(mem, other)
            if sim >= threshold:
                group.append(other)
                assigned.add(j)

        groups.append(group)

    return groups


def infer_topic_name(memories: List[Dict[str, Any]]) -> str:
    """Infer a topic name from a group of memories."""
    # Collect all keywords from the group
    all_keywords = set()
    for mem in memories:
        all_keywords |= extract_keywords(mem["content"])

    # Also include tags
    for mem in memories:
        metadata = mem.get("metadata") or {}
        tags = metadata.get("tags", [])
        all_keywords |= set(tags)

    if not all_keywords:
        return "general"

    # Score keywords by frequency
    keyword_count = defaultdict(int)
    for mem in memories:
        keywords = extract_keywords(mem["content"])
        metadata = mem.get("metadata") or {}
        keywords |= set(metadata.get("tags", []))
        for kw in keywords:
            keyword_count[kw] += 1

    # Get top keywords (by frequency across memories)
    top_keywords = sorted(keyword_count.items(), key=lambda x: -x[1])[:5]

    # Build topic name from top keywords
    topic_parts = [kw for kw, _ in top_keywords[:3]]

    if topic_parts:
        # CamelCase the topic name
        topic_name = "".join(p.capitalize() for p in topic_parts)
        return topic_name.lower().replace("-", "")

    return "general"


def generate_topic_summary(memories: List[Dict[str, Any]], topic_name: str) -> str:
    """Generate a summary for a topic from its memories."""
    if not memories:
        return ""

    # Take up to 10 most recent memories for summary
    recent = sorted(memories, key=lambda m: m.get("timestamp", ""), reverse=True)[:10]

    # Combine facts into a coherent summary
    facts = []
    for mem in recent:
        content = mem["content"].strip()
        if content and not content.endswith("."):
            content += "."
        facts.append(f"- {content}")

    summary = "\n".join(facts)
    return summary


def write_topic_file(
    project: str,
    topic_name: str,
    summary: str,
    memory_ids: List[int],
) -> Path:
    """Write a topic file to disk."""
    topics_dir = get_topics_dir(project)
    topics_dir.mkdir(parents=True, exist_ok=True)

    # Sanitize topic name for filename
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "-", topic_name.lower())
    filename = f"{safe_name}.md"
    filepath = topics_dir / filename

    # Build frontmatter
    frontmatter = f"""---
topic: {topic_name}
memory_ids: {json.dumps(memory_ids)}
---

"""

    # Build content
    content = f"""{frontmatter}# {topic_name.title()}

{summary}

---
_Generated by Cheapskate Agent Memory topicify_
"""

    # Write file
    filepath.write_text(content, encoding="utf-8")

    return filepath


def topicify_memories(
    project: str,
    memory_dir: Optional[Path] = None,
    threshold: float = 0.3,
    group_by: str = "auto",
    auto: bool = False,
) -> int:
    """
    Topicify memories - auto-group memories into topic files.

    Args:
        project: Project name
        memory_dir: Path to memory directory
        threshold: Similarity threshold for grouping (0.0 to 1.0)
        group_by: Grouping strategy: 'tags', 'vector', 'keywords', or 'auto'
        auto: Auto-create topics without prompting

    Returns:
        Exit code (0 for success, 1 for error)
    """
    try:
        # Load config and get database path
        if memory_dir:
            config_path = memory_dir / "config.yaml"
        else:
            config_path = None
        config = Config(config_path)
        db_path = config.database_path

        # Check if database exists
        if not db_path.exists():
            print(f"Memory not initialized. Run 'memory init' first.", file=sys.stderr)
            return 1

        # Connect to database
        db = Database(db_path)
        db.connect()

        # Get all memories for the project
        memories = db.list_memories(project=project, limit=1000)

        if not memories:
            print(f"No memories found for project '{project}'.")
            return 0

        print(f"Found {len(memories)} memories for project '{project}'")

        # Ensure topics directory exists
        topics_dir = get_topics_dir(project)
        topics_dir.mkdir(parents=True, exist_ok=True)

        if group_by == "tags":
            # Group by tags only
            groups = group_memories_by_tags(memories)

            for tag, group_memories in groups.items():
                topic_name = tag if tag != "untagged" else infer_topic_name(group_memories)
                memory_ids = [m["id"] for m in group_memories]
                summary = generate_topic_summary(group_memories, topic_name)

                # Update database
                db.upsert_topic(project, topic_name, summary, memory_ids)

                # Write topic file
                filepath = write_topic_file(project, topic_name, summary, memory_ids)
                print(f"  Created topic '{topic_name}' with {len(memory_ids)} memories -> {filepath}")

        elif group_by == "vector" or group_by == "keywords":
            # Group by semantic similarity
            groups = group_memories_by_similarity(memories, threshold)

            for i, group_memories in enumerate(groups):
                topic_name = infer_topic_name(group_memories)
                # Add index to make name unique
                if len(groups) > 1:
                    topic_name = f"{topic_name}-{i + 1}"

                memory_ids = [m["id"] for m in group_memories]
                summary = generate_topic_summary(group_memories, topic_name)

                # Update database
                db.upsert_topic(project, topic_name, summary, memory_ids)

                # Write topic file
                filepath = write_topic_file(project, topic_name, summary, memory_ids)
                print(f"  Created topic '{topic_name}' with {len(memory_ids)} memories -> {filepath}")

        else:
            # Auto mode: combine tags + similarity
            # First group by tags, then apply similarity within groups
            tag_groups = group_memories_by_tags(memories)

            topics_created = 0
            for tag, group_memories in tag_groups.items():
                if len(group_memories) <= 3:
                    # Small groups - single topic
                    topic_name = tag if tag != "untagged" else infer_topic_name(group_memories)
                    memory_ids = [m["id"] for m in group_memories]
                    summary = generate_topic_summary(group_memories, topic_name)

                    db.upsert_topic(project, topic_name, summary, memory_ids)
                    filepath = write_topic_file(project, topic_name, summary, memory_ids)
                    print(f"  Created topic '{topic_name}' with {len(memory_ids)} memories -> {filepath}")
                    topics_created += 1
                else:
                    # Large groups - apply similarity clustering
                    sim_groups = group_memories_by_similarity(group_memories, threshold)
                    for j, sim_memories in enumerate(sim_groups):
                        topic_name = infer_topic_name(sim_memories)
                        if len(sim_groups) > 1:
                            topic_name = f"{topic_name}-{j + 1}"

                        memory_ids = [m["id"] for m in sim_memories]
                        summary = generate_topic_summary(sim_memories, topic_name)

                        db.upsert_topic(project, topic_name, summary, memory_ids)
                        filepath = write_topic_file(project, topic_name, summary, memory_ids)
                        print(f"  Created topic '{topic_name}' with {len(memory_ids)} memories -> {filepath}")
                        topics_created += 1

            print(f"\nCreated {topics_created} topics")

        db.close()
        return 0

    except Exception as e:
        print(f"Error during topicify: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Auto-group memories into topic files")
    parser.add_argument(
        "--project",
        "-p",
        default=None,
        help="Project name (default: default)",
    )
    parser.add_argument(
        "--threshold",
        "-t",
        type=float,
        default=0.3,
        help="Similarity threshold (0.0 to 1.0, default: 0.3)",
    )
    parser.add_argument(
        "--group-by",
        "-g",
        choices=["auto", "tags", "vector", "keywords"],
        default="auto",
        help="Grouping strategy (default: auto)",
    )
    parser.add_argument(
        "--auto",
        "-a",
        action="store_true",
        help="Auto-create topics without prompting",
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=None,
        help="Memory directory path (default: ~/.memory)",
    )

    args = parser.parse_args()
    project = args.project or "default"

    sys.exit(topicify_memories(
        project=project,
        memory_dir=args.path,
        threshold=args.threshold,
        group_by=args.group_by,
        auto=args.auto,
    ))