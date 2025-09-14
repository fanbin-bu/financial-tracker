import os
from abc import ABC

import pandas as pd
import psycopg2
import yaml
from psycopg2.extras import RealDictCursor


class CSVProcessor(ABC):
    """Abstract base class for CSV processors"""

    # Subclasses should override these class attributes
    date_column_name = None
    description_column_name = None
    amount_column_name = None
    amount_multiplier = 1  # -1 to flip sign, 1 to keep as-is
    skip_patterns = []  # List of strings to skip if found in description (case insensitive)

    def process(self, file_path):
        """
        Process a CSV file and return standardized transaction data

        Args:
            file_path: Path to the CSV file

        Returns:
            List of dictionaries with keys: date, description, amount
        """
        df = pd.read_csv(file_path)
        df = self._prepare_dataframe(df)

        processed = []
        for _, row in df.iterrows():
            # Skip Costco transactions if this processor handles them separately
            if self._should_skip_transaction(row):
                continue

            transaction_data = self._extract_transaction_data(row)
            if transaction_data:
                processed.append(transaction_data)

        return processed

    def _prepare_dataframe(self, df):
        """
        Prepare the dataframe (e.g., convert date columns)

        Args:
            df: Raw pandas DataFrame

        Returns:
            Prepared pandas DataFrame
        """
        if self.date_column_name and self.date_column_name in df.columns:
            df[self.date_column_name] = pd.to_datetime(df[self.date_column_name])

        # Allow subclasses to consolidate columns
        df = self._consolidate_columns(df)
        return df

    def _consolidate_columns(self, df):
        """
        Consolidate multiple columns into standard format
        Subclasses can override this to handle special column structures

        Args:
            df: Prepared pandas DataFrame

        Returns:
            DataFrame with consolidated columns
        """
        return df

    def _extract_transaction_data(self, row):
        """
        Extract transaction data from a row using column attributes

        Args:
            row: Pandas Series representing a row

        Returns:
            Dictionary with keys: date, description, amount
            Returns None to skip this transaction
        """
        # If all required columns are defined, use default implementation
        if (
            self.date_column_name
            and self.description_column_name
            and self.amount_column_name
        ):
            return {
                "date": row[self.date_column_name],
                "description": row[self.description_column_name],
                "amount": float(row[self.amount_column_name]) * self.amount_multiplier,
            }

        # Otherwise, subclass must implement this method
        raise NotImplementedError(
            "Either define date_column_name, description_column_name, and amount_column_name "
            "class attributes, or override _extract_transaction_data method"
        )

    def _should_skip_transaction(self, row):
        """
        Determine if transaction should be skipped based on skip patterns

        Args:
            row: Pandas Series representing a row

        Returns:
            True if transaction should be skipped
        """
        if not self.skip_patterns or not self.description_column_name:
            return False

        # Check if description contains any skip patterns
        if self.description_column_name in row:
            description = str(row[self.description_column_name]).lower()
            return any(pattern.lower() in description for pattern in self.skip_patterns)

        return False


class CitiCSVProcessor(CSVProcessor):
    """Processor for Citi credit card CSV files"""

    date_column_name = "Date"
    description_column_name = "Description"
    amount_column_name = "Amount"  # Will be created from Debit/Credit
    amount_multiplier = 1
    skip_patterns = ["costco"]  # Skip Costco transactions

    def _consolidate_columns(self, df):
        """Consolidate Debit/Credit columns into single Amount column"""
        # Debit column has spending (positive), Credit column has payments (already negative)
        df["Amount"] = df["Debit"].fillna(0).astype(float) + df["Credit"].fillna(
            0
        ).astype(float)
        return df


class SmartlyCSVProcessor(CSVProcessor):
    """Processor for Smartly credit card CSV files"""

    date_column_name = "Date"
    description_column_name = "Name"
    amount_column_name = "Amount"
    amount_multiplier = -1  # Flip sign for Smartly format
    skip_patterns = ["costco"]  # Skip Costco transactions


class CostcoCSVProcessor(CSVProcessor):
    """Processor for Costco transactions CSV files"""

    date_column_name = "date"
    description_column_name = "description"
    amount_column_name = "amount"
    amount_multiplier = 1  # Keep original sign
    skip_patterns = []  # No patterns to skip

    def _extract_transaction_data(self, row):
        # Custom implementation to add COSTCO prefix
        return {
            "date": row[self.date_column_name],
            "description": f"COSTCO-{row[self.description_column_name]}",
            "amount": float(row[self.amount_column_name]) * self.amount_multiplier,
        }


class FinancialAnalyzer:
    """
    Financial transaction analyzer and data processor.

    This class processes multiple credit card CSV files, normalizes transaction data,
    and categorizes transactions with interactive rule-based categorization.
    Results are exported to PostgreSQL for Metabase dashboard visualization.

    Features:
    - Multi-format CSV processing (Citi, Smartly credit cards, Costco transactions)
    - Intelligent merchant name extraction and cleaning
    - Interactive rule-based transaction categorization
    - Auto-updating YAML configuration
    - PostgreSQL export with optimized schema for BI tools
    - Seamless Metabase integration
    """

    # Available categories for interactive selection
    AVAILABLE_CATEGORIES = [
        "Food",
        "Travel",
        "Shopping",
        "Utilities",
        "Healthcare",
        "Entertainment",
        "Services",
        "Payment",
    ]

    def __init__(
        self,
        csv_folder="csv",
        db_config=None,
        config_file="categorization_config.yaml",
        csv_processor_mapping=None,
    ):
        """
        Initialize the financial analyzer.

        Args:
            csv_folder: Path to folder containing CSV files
            db_config: PostgreSQL connection configuration
            config_file: Path to categorization configuration file
            csv_processor_mapping: Dict mapping CSV filenames to processor classes
        """
        self.csv_folder = csv_folder
        self.combined_data = None

        # Default mapping of CSV files to processors
        self.csv_processor_mapping = csv_processor_mapping or {
            "Year to date.CSV": CitiCSVProcessor(),
            "Credit Card - 1604_01-01-2025_08-29-2025.csv": SmartlyCSVProcessor(),
            "costco_transactions.csv": CostcoCSVProcessor(),
        }
        self.db_config = db_config or {
            "host": "localhost",
            "database": "financial_tracker",
            "user": "postgres",
            "password": "postgres",
            "port": 5432,
        }
        self.db_conn = None
        self.config_file = config_file
        self.categorization_config = self.load_categorization_config(config_file)

    def load_categorization_config(self, config_file):
        """Load categorization configuration from YAML file"""
        try:
            with open(config_file, "r") as f:
                config = yaml.safe_load(f)
            print(f"Loaded categorization config from {config_file}")
            return config
        except FileNotFoundError:
            print(f"Config file {config_file} not found, using default categorization")
            return {
                "categories": {
                    "Food": ["restaurant", "cafe", "food"],
                    "Transportation": ["uber", "lyft", "gas", "parking"],
                    "Shopping": ["amazon", "store"],
                    "Other": [],
                },
                "default_category": "Other",
            }
        except yaml.YAMLError as e:
            print(f"Error parsing YAML config file: {e}. Using default categorization")
            return {"categories": {"Other": []}, "default_category": "Other"}

    def load_and_process_data(self):
        """Load and process all CSV files using registered processors"""
        if not os.path.exists(self.csv_folder):
            raise ValueError(f"CSV folder '{self.csv_folder}' does not exist")

        # Find all CSV files that have processors registered
        available_files = set(os.listdir(self.csv_folder))
        registered_files = set(self.csv_processor_mapping.keys())
        csv_files = available_files.intersection(registered_files)

        if not csv_files:
            print(f"Available files: {sorted(available_files)}")
            print(f"Registered files: {sorted(registered_files)}")
            raise ValueError(
                f"No registered CSV files found in '{self.csv_folder}' folder"
            )

        print(f"Processing {len(csv_files)} registered CSV files: {sorted(csv_files)}")

        all_data = []

        # Process each registered CSV file
        for csv_file in csv_files:
            file_path = os.path.join(self.csv_folder, csv_file)
            processor = self.csv_processor_mapping[csv_file]

            print(f"Processing {csv_file} with {processor.__class__.__name__}...")

            try:
                processed_data = processor.process(file_path)
                all_data.extend(processed_data)
                print(f"  Processed {len(processed_data)} transactions from {csv_file}")
            except Exception as e:
                print(f"  Error processing {csv_file}: {e}")
                continue

        if not all_data:
            raise ValueError("No data was successfully processed from any CSV files")

        # Combine data into DataFrame
        self.combined_data = pd.DataFrame(all_data)
        self.combined_data = self.combined_data.sort_values("date").reset_index(
            drop=True
        )

        # Add raw_description column (keep original) and clean description
        self.combined_data["raw_description"] = self.combined_data["description"]
        self.combined_data["description"] = self.combined_data["raw_description"].apply(
            self.extract_merchant_name
        )

        # Add categories using rule-based categorization
        print("Using rule-based categorization...")
        self.combined_data["category"] = self.combined_data.apply(
            lambda row: self.categorize_transaction_with_amount(
                row["description"], row["amount"]
            ),
            axis=1,
        )
        print(f"Categorized {len(self.combined_data)} transactions")

        # Add year_month column for database export
        self.combined_data["year_month"] = self.combined_data["date"].dt.strftime(
            "%Y-%m"
        )

        return self.combined_data

    def extract_merchant_name(self, raw_description):
        """Extract clean merchant name from raw description (max 2 words)"""
        desc_lower = raw_description.lower()

        # Common merchants with clean names (max 2 words)
        if "tesla" in desc_lower and (
            "supercharger" in desc_lower or "charge" in desc_lower
        ):
            return "TESLA Charging"
        elif "blink charging" in desc_lower or "blink" in desc_lower:
            return "Blink Charging"
        elif "amazon" in desc_lower:
            return "AMAZON"
        elif "starbucks" in desc_lower:
            return "STARBUCKS"
        elif "delta" in desc_lower and "air" in desc_lower:
            return "DELTA Airlines"
        elif "uber" in desc_lower:
            return "UBER"
        elif "lyft" in desc_lower:
            return "LYFT"
        elif "safeway" in desc_lower:
            return "SAFEWAY"
        elif "qfc" in desc_lower:
            return "QFC"
        elif "at&t" in desc_lower:
            return "AT&T"
        elif "t&t" in desc_lower and "supermarket" in desc_lower:
            return "T&T Supermarket"
        elif "puget sound energy" in desc_lower:
            return "Puget Sound"
        elif "progressive" in desc_lower and "insurance" in desc_lower:
            return "Progressive Insurance"
        elif "rei" in desc_lower and ("rei " in desc_lower or "rei.com" in desc_lower):
            return "REI"
        elif "best buy" in desc_lower:
            return "Best Buy"
        elif "target" in desc_lower:
            return "Target"
        elif "home depot" in desc_lower:
            return "Home Depot"
        elif "ikea" in desc_lower:
            return "IKEA"
        elif "uscis" in desc_lower:
            return "USCIS"
        elif "us treas" in desc_lower and ("tax" in desc_lower or "pymt" in desc_lower):
            return "US Treasury"
        elif "autopay" in desc_lower or "payment" in desc_lower:
            return "Payment"
        elif "walgreens" in desc_lower:
            return "WALGREENS"
        elif "cvs" in desc_lower:
            return "CVS"
        elif "shell" in desc_lower:
            return "SHELL"
        elif "chevron" in desc_lower:
            return "CHEVRON"
        elif "arco" in desc_lower:
            return "ARCO"
        elif "mcdonald" in desc_lower:
            return "McDonalds"
        elif "subway" in desc_lower:
            return "SUBWAY"
        elif "trader joe" in desc_lower:
            return "Trader Joes"
        elif "whole foods" in desc_lower:
            return "Whole Foods"
        elif "walmart" in desc_lower or "wm supercenter" in desc_lower:
            return "WALMART"
        elif "fred meyer" in desc_lower or "fred-meyer" in desc_lower:
            return "Fred Meyer"
        elif "goodwill" in desc_lower:
            return "GOODWILL"
        elif "netflix" in desc_lower:
            return "NETFLIX"
        elif "spotify" in desc_lower:
            return "SPOTIFY"
        elif "apple" in desc_lower and (
            "store" in desc_lower or "itunes" in desc_lower
        ):
            return "Apple Store"
        elif "google" in desc_lower:
            return "GOOGLE"
        elif "microsoft" in desc_lower:
            return "MICROSOFT"
        elif "too good to go" in desc_lower:
            return "Too Good"
        elif "summit" in desc_lower and "snoqualmie" in desc_lower:
            return "Summit Snoqualmie"
        elif "claire" in desc_lower:
            return "CLAIRE"
        elif "ten seconds" in desc_lower:
            return "Ten Seconds"
        elif "legoland" in desc_lower:
            return "LEGOLAND"
        elif "dough zone" in desc_lower:
            return "Dough Zone"
        elif "pay by phone" in desc_lower or "paybyphone" in desc_lower:
            return "Parking"
        elif "spokane" in desc_lower:
            # Extract business name for Spokane transactions
            if "hotel" in desc_lower or "club" in desc_lower:
                return "Spokane Club"
            elif "restaurant" in desc_lower or "kitchen" in desc_lower:
                return "Spokane Restaurant"
            else:
                return "Spokane Business"
        else:
            # For unknown merchants, extract first meaningful words (max 2)
            clean_desc = raw_description.strip()

            # Remove common payment processing prefixes
            prefixes_to_remove = ["SQ *", "TST*", "SP ", "FSP*", "6602-"]
            for prefix in prefixes_to_remove:
                if clean_desc.startswith(prefix):
                    clean_desc = clean_desc[len(prefix) :].strip()

            # Split into words and clean
            words = clean_desc.split()
            clean_words = []

            for word in words:
                # Skip phone numbers (contains digits and dashes/dots)
                if any(char.isdigit() for char in word) and any(
                    char in word for char in ["-", ".", "/"]
                ):
                    continue
                # Skip state abbreviations at the end
                if len(word) == 2 and word.isupper():
                    continue
                # Skip common location words
                if word.lower() in [
                    "phone",
                    "number:",
                    "folio",
                    "arrive:",
                    "depart:",
                    "www",
                    "com",
                    "ecom",
                ]:
                    continue
                # Keep meaningful words
                if len(word) > 1:
                    clean_words.append(word.title())

                # Limit to 2 words
                if len(clean_words) >= 2:
                    break

            if clean_words:
                return " ".join(clean_words[:2])
            else:
                # Fallback: first word only
                first_word = words[0] if words else raw_description
                return first_word.title()[:15]

    def categorize_transaction_with_amount(self, description, amount):
        """Categorize transaction with access to both description and amount"""
        desc_lower = description.lower()

        # Check if this is a Costco transaction with amount > 100
        if desc_lower.startswith("costco-") and amount > 100:
            return "Shopping"

        # First check existing categories and their keywords
        for category, keywords in self.categorization_config["categories"].items():
            if any(keyword.lower() in desc_lower for keyword in keywords):
                return category

        # If no match found, prompt user for categorization
        return self.prompt_user_for_category(description, amount)

    def prompt_user_for_category(self, description, amount):
        """Prompt user to categorize unknown transaction and update config"""
        print(f"\n🔍 Unknown transaction found: '{description}: {amount}'")
        print("Available categories:")

        for i, category in enumerate(self.AVAILABLE_CATEGORIES, 1):
            print(f"  {i}. {category}")

        while True:
            try:
                prompt = f"\nSelect category (1-{len(self.AVAILABLE_CATEGORIES)}): "
                choice = input(prompt).strip()
                if not choice:
                    continue

                choice_idx = int(choice) - 1
                if 0 <= choice_idx < len(self.AVAILABLE_CATEGORIES):
                    selected_category = self.AVAILABLE_CATEGORIES[choice_idx]

                    # Extract key terms from description for future matching
                    key_term = self.extract_key_term_for_config(description)

                    # Update config with new keyword
                    self.update_config_with_new_keyword(selected_category, key_term)

                    print(f"✅ '{description}' categorized as '{selected_category}'")
                    print(f"📝 Added '{key_term}' to {selected_category} keywords")

                    return selected_category
                else:
                    max_cat = len(self.AVAILABLE_CATEGORIES)
                    print(f"Please enter a number between 1 and {max_cat}")

            except ValueError:
                print("Please enter a valid number")
            except KeyboardInterrupt:
                print(f"\n⚠️  Using default category 'Other' for '{description}'")
                return self.categorization_config.get("default_category", "Other")

    def extract_key_term_for_config(self, description):
        """Extract meaningful terms from description for config updates"""
        # Remove common prefixes and extract meaningful part
        prefixes_to_remove = ["sq *", "tst*", "sp ", "fsp*", "6602-"]
        clean_desc = description

        for prefix in prefixes_to_remove:
            if clean_desc.lower().startswith(prefix.lower()):
                clean_desc = clean_desc[len(prefix) :].strip()
                break

        # Take first 1-2 meaningful words
        words = clean_desc.split()
        meaningful_words = []

        for word in words[:3]:  # Look at first 3 words max
            # Skip numbers, states, and common meaningless words
            skip_words = ["inc", "llc", "com", "www", "phone", "number"]
            if len(word) > 2 and not word.isdigit() and word.lower() not in skip_words:
                meaningful_words.append(word.lower())
                if len(meaningful_words) >= 2:
                    break

        if meaningful_words:
            return " ".join(meaningful_words)
        else:
            # Fallback: use first word if no meaningful words found
            return words[0].lower() if words else description.lower()[:10]

    def update_config_with_new_keyword(self, category, keyword):
        """Update the YAML config file with new keyword"""
        # Add keyword to in-memory config
        if category not in self.categorization_config["categories"]:
            self.categorization_config["categories"][category] = []

        if keyword not in self.categorization_config["categories"][category]:
            self.categorization_config["categories"][category].append(keyword)

        # Write updated config back to file
        try:
            with open(self.config_file, "w") as f:
                yaml.dump(
                    self.categorization_config,
                    f,
                    default_flow_style=False,
                    sort_keys=False,
                )
            print(f"💾 Config file updated: {self.config_file}")
        except Exception as e:
            print(f"⚠️  Error updating config file: {e}")

    def connect_to_postgres(self):
        """Connect to PostgreSQL database"""
        try:
            self.db_conn = psycopg2.connect(**self.db_config)
            host = self.db_config["host"]
            port = self.db_config["port"]
            print(f"Connected to PostgreSQL at {host}:{port}")
            return True
        except psycopg2.OperationalError as e:
            print(f"Failed to connect to PostgreSQL: {e}")
            print("Make sure PostgreSQL is running and database exists")
            return False
        except Exception as e:
            print(f"Unexpected error connecting to PostgreSQL: {e}")
            return False

    def create_postgres_table(self, table_name="financial_transactions"):
        """Create PostgreSQL table for financial data"""
        if not self.db_conn:
            if not self.connect_to_postgres():
                return False

        create_table_sql = f"""
        DROP TABLE IF EXISTS {table_name};
        
        CREATE TABLE {table_name} (
            id SERIAL PRIMARY KEY,
            transaction_date DATE NOT NULL,
            raw_description TEXT NOT NULL,
            description TEXT NOT NULL,
            amount DECIMAL(10, 2) NOT NULL,
            category VARCHAR(100) NOT NULL,
            year_month VARCHAR(7) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX idx_transaction_date ON {table_name}(transaction_date);
        CREATE INDEX idx_category ON {table_name}(category);
        CREATE INDEX idx_year_month ON {table_name}(year_month);
        CREATE INDEX idx_description ON {table_name}(description);
        """

        try:
            with self.db_conn.cursor() as cursor:
                cursor.execute(create_table_sql)
                self.db_conn.commit()
            print(f"Table '{table_name}' created successfully")
            return True
        except Exception as e:
            print(f"Error creating table: {e}")
            self.db_conn.rollback()
            return False

    def export_to_postgres(self, table_name="financial_transactions"):
        """Export the processed data to PostgreSQL"""
        if self.combined_data is None:
            self.load_and_process_data()

        if not self.db_conn:
            if not self.connect_to_postgres():
                return False

        if not self.create_postgres_table(table_name):
            return False

        # Prepare and insert data
        try:
            with self.db_conn.cursor() as cursor:
                for _, row in self.combined_data.iterrows():
                    insert_sql = f"""
                    INSERT INTO {table_name}
                    (transaction_date, raw_description, description, amount,
                     category, year_month)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """

                    cursor.execute(
                        insert_sql,
                        (
                            row["date"].date(),
                            row["raw_description"],
                            row["description"],
                            float(row["amount"]),
                            row["category"],
                            str(row["year_month"]),
                        ),
                    )

                self.db_conn.commit()

            count = len(self.combined_data)
            print(f"Successfully inserted {count} transactions into PostgreSQL")

            # Show sample data
            with self.db_conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    f"SELECT * FROM {table_name} ORDER BY transaction_date DESC LIMIT 5"
                )
                sample_data = cursor.fetchall()
                print("\nSample data in PostgreSQL:")
                for row in sample_data:
                    print(dict(row))

            return True
        except Exception as e:
            print(f"Error inserting data: {e}")
            self.db_conn.rollback()
            return False


def main():
    # Initialize analyzer with csv folder
    analyzer = FinancialAnalyzer()

    # Load and process data
    print("Loading and processing data...")
    combined_data = analyzer.load_and_process_data()
    print(f"Processed {len(combined_data)} transactions")

    # Export to PostgreSQL
    print("\n" + "=" * 50)
    print("EXPORTING TO POSTGRESQL")
    print("=" * 50)
    postgres_success = analyzer.export_to_postgres()

    if postgres_success:
        print("\nData successfully exported to PostgreSQL!")
        print("You can now connect Metabase to PostgreSQL and create dashboards.")
        print("PostgreSQL connection details:")
        print("- Host: localhost")
        print("- Port: 5432")
        print("- Database: financial_tracker")
        print("- User: postgres")
        print("- Table: financial_transactions")


if __name__ == "__main__":
    main()
