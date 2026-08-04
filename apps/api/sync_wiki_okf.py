import os
import glob

def sync_all_legal_docs_to_okf():
    base_legal_dir = r"d:\bitsnbytes\agreements\legal-docs"
    dst_base_dir = r"d:\motherboard\data\company-knowledge\legal"

    sources = [
        ("notion-wiki", "*.md", "wiki", "Policy Rule", ["legal", "governance", "notion-wiki"]),
        ("mca", "*.txt", "mca", "Policy Rule", ["legal", "statutory", "mca", "incorporation"]),
        ("bnb-rules", "*.txt", "rules", "Policy Rule", ["legal", "governance", "operating-manual"]),
        (os.path.join("bnb-docs-", "txt", "notices"), "*.txt", "notices", "Template", ["legal", "notice", "template"]),
        (os.path.join("bnb-docs-", "txt", "onboarding"), "*.txt", "onboarding", "Template", ["legal", "onboarding", "template"]),
    ]

    total_synced = 0
    for src_rel, pattern, dst_sub, concept_type, tags in sources:
        src_path = os.path.join(base_legal_dir, src_rel)
        dst_path = os.path.join(dst_base_dir, dst_sub)
        os.makedirs(dst_path, exist_ok=True)

        files = glob.glob(os.path.join(src_path, pattern))
        print(f"Scanning {src_path}: found {len(files)} files")

        for file_path in files:
            base_name = os.path.basename(file_path)
            clean_title = os.path.splitext(base_name)[0]
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            out_filename = clean_title + ".md"
            okf_content = f"""---
type: {concept_type}
title: {clean_title}
description: Official bits&bytes legal document from {src_rel}
tags: {tags}
timestamp: 2026-08-04T00:00:00Z
---

# {clean_title}

{content}
"""
            out_filepath = os.path.join(dst_path, out_filename)
            with open(out_filepath, "w", encoding="utf-8") as f:
                f.write(okf_content)
            total_synced += 1

    print(f"Successfully synced a total of {total_synced} legal documents into {dst_base_dir}")

if __name__ == "__main__":
    sync_all_legal_docs_to_okf()
