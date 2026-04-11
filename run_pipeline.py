"""
Run the full pipeline with all 15 queries.
Drops and recreates the database for a clean run.
"""
import logging
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)

from vanl.research_pipeline.config import DB_PATH

# Delete old database for clean run
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)
    print(f"Removed old database: {DB_PATH}")

from vanl.research_pipeline.pipeline import ResearchPipeline

def main():
    pipeline = ResearchPipeline()
    stats = pipeline.run(max_per_query=10)

    print()
    print("=" * 60)
    print("PIPELINE RUN COMPLETE")
    print("=" * 60)
    print(stats)
    print()
    print("Database Statistics:")
    db_stats = pipeline.get_database_stats()
    for k, v in db_stats.items():
        if isinstance(v, dict):
            print(f"  {k}:")
            for kk, vv in v.items():
                print(f"    {kk}: {vv}")
        else:
            print(f"  {k}: {v}")
    print("=" * 60)

    # Show sample extracted data
    from vanl.research_pipeline.search import DatasetSearch
    search = DatasetSearch(pipeline.conn)

    print("\nUnique Materials Found:")
    for m in search.list_materials():
        print(f"  {m['component']}: {m['paper_count']} papers (avg conf: {m['avg_confidence']:.2f})")

    print("\nSynthesis Methods Found:")
    for m in search.list_methods():
        print(f"  {m['method']}: {m['paper_count']} papers")

    print("\nApplications:")
    for a in search.list_applications():
        print(f"  {a['application']}: {a['count']} papers")

    print("\nSample: papers containing 'graphene' + 'supercapacitor':")
    results = search.search(material="graphene", application="supercapacitor", limit=5)
    for r in results:
        print(f"  [{r.get('year','?')}] {r['title'][:80]}...")
        if r.get('materials'):
            mats = [m['component'] for m in r['materials']]
            print(f"    Materials: {', '.join(mats)}")
        if r.get('eis_data'):
            for e in r['eis_data']:
                parts = []
                if e.get('Rct_ohm'): parts.append(f"Rct={e['Rct_ohm']}")
                if e.get('capacitance_F_g'): parts.append(f"Cs={e['capacitance_F_g']} F/g")
                if parts:
                    print(f"    EIS: {', '.join(parts)}")

    pipeline.close()

if __name__ == "__main__":
    main()
