import sqlite3

conn = sqlite3.connect("vanl/datasets/research/papers.db")
conn.row_factory = sqlite3.Row

print("=== DATABASE STATS ===")
print(f"Papers: {conn.execute('SELECT COUNT(*) FROM papers').fetchone()[0]}")
print(f"Processed: {conn.execute('SELECT COUNT(*) FROM papers WHERE processed=1').fetchone()[0]}")
print(f"Materials: {conn.execute('SELECT COUNT(*) FROM materials').fetchone()[0]}")
print(f"Unique materials: {conn.execute('SELECT COUNT(DISTINCT component) FROM materials').fetchone()[0]}")
print(f"EIS records: {conn.execute('SELECT COUNT(*) FROM eis_data').fetchone()[0]}")
print(f"Synthesis: {conn.execute('SELECT COUNT(*) FROM synthesis').fetchone()[0]}")
print()

print("=== TOP 15 MATERIALS ===")
for r in conn.execute("SELECT component, COUNT(DISTINCT paper_id) as cnt FROM materials GROUP BY component ORDER BY cnt DESC LIMIT 15").fetchall():
    print(f"  {r['component']:30s} papers={r['cnt']}")
print()

print("=== APPLICATIONS ===")
for r in conn.execute("SELECT application, COUNT(*) as cnt FROM papers WHERE application IS NOT NULL GROUP BY application ORDER BY cnt DESC").fetchall():
    print(f"  {r['application']:20s} {r['cnt']}")
print()

print("=== EIS DATA SAMPLE (Rct not null) ===")
for r in conn.execute("SELECT Rs_ohm, Rct_ohm, capacitance_F_g, electrolyte FROM eis_data WHERE Rct_ohm IS NOT NULL LIMIT 10").fetchall():
    print(f"  Rs={r['Rs_ohm']}, Rct={r['Rct_ohm']}, Cap={r['capacitance_F_g']}, Elec={r['electrolyte']}")

print()
print("=== SYNTHESIS METHODS ===")
for r in conn.execute("SELECT method, COUNT(*) as cnt FROM synthesis WHERE method IS NOT NULL GROUP BY method ORDER BY cnt DESC").fetchall():
    print(f"  {r['method']:25s} {r['cnt']}")

print()
print("=== SAMPLE PAPER TITLES ===")
for r in conn.execute("SELECT title FROM papers WHERE processed=1 LIMIT 5").fetchall():
    print(f"  {r['title'][:100]}")

print()
print("=== EIS PARAMETER RANGES ===")
stats = conn.execute("""
    SELECT 
        COUNT(*) as count,
        AVG(Rs_ohm) as avg_Rs, MIN(Rs_ohm) as min_Rs, MAX(Rs_ohm) as max_Rs,
        AVG(Rct_ohm) as avg_Rct, MIN(Rct_ohm) as min_Rct, MAX(Rct_ohm) as max_Rct,
        AVG(capacitance_F_g) as avg_cap, MIN(capacitance_F_g) as min_cap, MAX(capacitance_F_g) as max_cap
    FROM eis_data
    WHERE Rs_ohm IS NOT NULL OR Rct_ohm IS NOT NULL
""").fetchone()
print(f"  Total EIS with data: {stats['count']}")
print(f"  Rs range:  {stats['min_Rs']} - {stats['max_Rs']} (avg {stats['avg_Rs']})")
print(f"  Rct range: {stats['min_Rct']} - {stats['max_Rct']} (avg {stats['avg_Rct']})")
print(f"  Cap range: {stats['min_cap']} - {stats['max_cap']} (avg {stats['avg_cap']})")

conn.close()
