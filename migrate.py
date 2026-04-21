import sqlite3
conn = sqlite3.connect('/app/data/radcoin_bot.db')
cursor = conn.cursor()
cursor.execute("PRAGMA table_info(users)")
existing = [col[1] for col in cursor.fetchall()]
if 'chest_common' not in existing:
    cursor.execute("ALTER TABLE users ADD COLUMN chest_common INTEGER DEFAULT 0")
if 'chest_rare' not in existing:
    cursor.execute("ALTER TABLE users ADD COLUMN chest_rare INTEGER DEFAULT 0")
if 'chest_epic' not in existing:
    cursor.execute("ALTER TABLE users ADD COLUMN chest_epic INTEGER DEFAULT 0")
if 'chest_legendary' not in existing:
    cursor.execute("ALTER TABLE users ADD COLUMN chest_legendary INTEGER DEFAULT 0")
conn.commit()
conn.close()
print("✅ Готово")
