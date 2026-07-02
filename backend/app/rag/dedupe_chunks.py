from __future__ import annotations

import argparse

from infra.database.postgres import get_conn, release_conn


def find_duplicate_chunks(limit: int = 20) -> list[tuple[str, int]]:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT content, COUNT(*) AS duplicate_count
                FROM chunks
                GROUP BY content
                HAVING COUNT(*) > 1
                ORDER BY duplicate_count DESC
                LIMIT %s
                """,
                (limit,),
            )
            return cur.fetchall()
    finally:
        release_conn(conn)


def remove_duplicate_chunks(dry_run: bool = True) -> int:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*)
                FROM chunks c
                WHERE c.id NOT IN (
                    SELECT MIN(id)
                    FROM chunks
                    GROUP BY content
                )
                """
            )
            duplicate_count = cur.fetchone()[0]

            if dry_run or duplicate_count == 0:
                conn.rollback()
                return duplicate_count

            cur.execute(
                """
                DELETE FROM chunks c
                WHERE c.id NOT IN (
                    SELECT MIN(id)
                    FROM chunks
                    GROUP BY content
                )
                """
            )

            cur.execute(
                """
                DELETE FROM documents d
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM chunks c
                    WHERE c.document_id = d.id
                )
                """
            )

        conn.commit()
        return duplicate_count
    except Exception:
        conn.rollback()
        raise
    finally:
        release_conn(conn)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Find or remove duplicated RAG chunks from the database."
    )
    parser.add_argument("--apply", action="store_true", help="Delete duplicated chunks.")
    parser.add_argument("--preview", type=int, default=10)
    args = parser.parse_args()

    duplicates = find_duplicate_chunks(limit=args.preview)
    if duplicates:
        print("Duplicate chunk groups:")
        for content, count in duplicates:
            print(f"- {count}x {content[:160]}")
    else:
        print("No duplicate chunk groups found.")

    duplicate_count = remove_duplicate_chunks(dry_run=not args.apply)
    if args.apply:
        print(f"Removed {duplicate_count} duplicated chunks.")
        print("Restart the app process to rebuild the in-memory FAISS index without deleted chunks.")
    else:
        print(f"Dry-run: {duplicate_count} duplicated chunks would be removed.")
        print("Run again with --apply to delete them.")


if __name__ == "__main__":
    main()
