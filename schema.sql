PRAGMA foreign_keys = ON;

-- -------------------------------
-- Units: Part 1 (Property details)
-- -------------------------------
CREATE TABLE IF NOT EXISTS units (
  unit_key TEXT PRIMARY KEY,              -- e.g., lower(trim(parcel_address || zip || unit_id))
  parcel_address TEXT NOT NULL,
  neighborhood TEXT,
  zip_code INTEGER,
  county_name TEXT,
  state TEXT,
  msa_name TEXT,
  new_construction TEXT,                  -- 'Yes' or 'No'
  rehabilitation TEXT,                    -- 'Yes' or 'No'
  year_built INTEGER,
  unit_type TEXT,                         -- e.g., Single family (detached), Duplex, etc.
  square_footage REAL,
  bedrooms INTEGER,
  bathrooms REAL,
  other_features TEXT,
  latitude REAL,
  longitude REAL,
  unit_number TEXT                    -- optional label e.g., "Unit A2"
);

-- ---------------------------------
-- Transactions: Part 2 (many-to-one)
-- ---------------------------------
CREATE TABLE IF NOT EXISTS transactions (
  txn_id TEXT PRIMARY KEY,
  unit_key TEXT NOT NULL,
  year_acquired_by_clt TEXT,      -- ISO date (YYYY-MM-DD)
  year_sold TEXT,                 -- ISO date (YYYY-MM-DD)
  initial_acquisition_cost REAL,
  subsidy_amount REAL,
  subsidy_source TEXT,
  subsidy_purpose TEXT,
  list_price REAL,
  fee_simple_appraisal_value REAL,
  leasehold_appraised REAL,
  appraised_market_value REAL,
  purchase_price REAL,
  write_down REAL,
  base_price REAL,
  loan_amount REAL,
  loan_type TEXT,
  lender_name TEXT,
  loan_term_years REAL,
  monthly_payments REAL,
  monthly_taxes_and_insurance REAL,
  land_fee REAL,
  interest_rate REAL,
  seller_equity_amount REAL,
  additional_repair_amount REAL,
  additional_repair_purpose TEXT,
  additional_repair_source TEXT,
  household_income_at_move_in REAL,
  household_income_at_move_out REAL,
  resale_formula TEXT,
  length_of_tenure REAL,
  time_on_market_months REAL,
  affordability_relative_to_market REAL,  -- store 0–100%
  household_size INTEGER,
  household_income_to_AMI_percent REAL,
  loan_remaining_previous_seller REAL,
  FOREIGN KEY(unit_key) REFERENCES units(unit_key) ON UPDATE CASCADE ON DELETE CASCADE
);

-- ---------------------------------------------
-- Acquisition Strategy: Part 3 (1-to-1 per unit)
-- ---------------------------------------------
CREATE TABLE IF NOT EXISTS acquisition_strategy (
  unit_key TEXT PRIMARY KEY,
  acquisition_criteria_type TEXT,
  acquisition_strategy_description TEXT,
  exclusion_criteria TEXT,
  FOREIGN KEY(unit_key) REFERENCES units(unit_key) ON UPDATE CASCADE ON DELETE CASCADE
);
