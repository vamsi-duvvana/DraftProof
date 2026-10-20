# DraftProof Architecture & Rule Management Guidelines

This document outlines the strict coding and design constraints established for this repository.

## 1. Decoupling Words, Topics, and Dictionaries from Source Code
All synonym dictionaries, phrase rewrites, adverbs, qualifiers, determiners, conjunctions, protected scientific terms, AI tell patterns, code personas, and academic discipline taxonomies reside in structured JSON files under `rules/`.

## 2. Hierarchical Academic Discipline Taxonomy (`rules/academic/taxonomy/`)
All academic topics, research sub-fields, author pools, and prestigious journal mappings reside in dedicated discipline subfolders:
- `rules/academic/taxonomy/computer_science/`
- `rules/academic/taxonomy/engineering_physics/`
- `rules/academic/taxonomy/mathematics_statistics/`
- `rules/academic/taxonomy/quantitative_finance/`
- `rules/academic/taxonomy/medical_life_sciences/`

## 3. JSON Prompt Metadata & Rule Formatting (`__prompt__`)
- **JSON Objects**: Contain a root `"__prompt__"` key with role definition, task rules, and negative prompting.
- **JSON Arrays**: Contain `{"__prompt__": "..."}` at index 0.
- `draftproof.core.rules` automatically strips `"__prompt__"` metadata on load and applies the Load-Time Vocab Hygiene Firewall (`filter_output_vocab`).

## 4. Clean `src/draftproof/core/__init__.py` & Lazy Loading
- `src/draftproof/core/__init__.py` contains docstrings only (no eager submodule imports).
- `streamlit_app.py` executes `st.set_page_config()` and `render_traffic_offload_guard()` immediately before lazy-loading active UI modules.
