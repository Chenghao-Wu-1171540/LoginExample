
CREATE TYPE user_role AS ENUM ('volunteer', 'event_leader', 'admin');
CREATE TYPE user_status AS ENUM ('active', 'inactive');
CREATE TYPE attendance_status AS ENUM ('pending', 'attended', 'absent');

CREATE TABLE users (
  user_id SERIAL PRIMARY KEY,
  username VARCHAR(50) NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  full_name VARCHAR(100) NOT NULL,
  email VARCHAR(255) NOT NULL UNIQUE,
  home_address VARCHAR(255),
  contact_number VARCHAR(20),
  profile_image VARCHAR(255) DEFAULT 'default_profile.jpg',
  environmental_interests TEXT,
  role user_role NOT NULL DEFAULT 'volunteer',
  status user_status NOT NULL DEFAULT 'active',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE events (
  event_id SERIAL PRIMARY KEY,
  event_name VARCHAR(100) NOT NULL,
  location VARCHAR(255) NOT NULL,
  event_date DATE NOT NULL,
  start_time TIME NOT NULL,
  duration INTEGER NOT NULL, -- minutes
  description TEXT,
  supplies TEXT,
  safety_instructions TEXT,
  event_leader_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE eventregistrations (
  registration_id SERIAL PRIMARY KEY,
  event_id INTEGER NOT NULL REFERENCES events(event_id) ON DELETE CASCADE,
  volunteer_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  attendance attendance_status DEFAULT 'pending',
  UNIQUE(event_id, volunteer_id)
);

CREATE TABLE eventoutcomes (
  outcome_id SERIAL PRIMARY KEY,
  event_id INTEGER NOT NULL REFERENCES events(event_id) ON DELETE CASCADE,
  num_attendees INTEGER DEFAULT 0,
  bags_collected INTEGER DEFAULT 0,
  recyclables_sorted INTEGER DEFAULT 0,
  other_achievements TEXT,
  recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE feedback (
  feedback_id SERIAL PRIMARY KEY,
  event_id INTEGER NOT NULL REFERENCES events(event_id) ON DELETE CASCADE,
  volunteer_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  rating INTEGER CHECK (rating BETWEEN 1 AND 5),
  comments TEXT,
  submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(event_id, volunteer_id)
);

CREATE INDEX idx_events_date ON events(event_date);