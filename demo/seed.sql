CREATE TABLE users (
  id INTEGER PRIMARY KEY,
  email TEXT NOT NULL,
  name TEXT,
  legacy_flag INTEGER
);
CREATE TABLE orders (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL,
  total_cents INTEGER NOT NULL
);
INSERT INTO users (email, name, legacy_flag) VALUES
  ('a@x.com', 'Ann', 1),
  ('b@x.com', 'Ben', NULL),
  ('c@x.com', 'Cara', 0);
INSERT INTO orders (user_id, total_cents) VALUES
  (1, 1200),
  (1, 800),
  (2, 450);
