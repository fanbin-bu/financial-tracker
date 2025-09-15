#!/usr/bin/env python3
"""
Metabase Dashboard Creation Script

This script creates a financial tracking dashboard in Metabase using the SQL queries
found in the metabase/ folder. It sets up field filters and organizes cards in a
logical layout.

Requirements:
- metabase-api package: pip install metabase-api
- python-dotenv package: pip install python-dotenv
- Valid Metabase credentials in .env file

Environment Variables (create a .env file):
METABASE_URL=http://localhost:3000
METABASE_USERNAME=your_username
METABASE_PASSWORD=your_password
METABASE_DATABASE_ID=1
"""

import os

from dotenv import load_dotenv
from metabase_api import Metabase_API

# Load environment variables from .env file
load_dotenv()

# Define reusable parameter templates
COMMON_PARAMETERS = {
    "year_month": {
        "type": "string/=",
        "target": ["dimension", ["template-tag", "year_month"]],
        "name": "Year Month",
        "slug": "year_month",
        "isMultiSelect": True,
    },
    "exclude_spending": {
        "type": "string/contains",
        "target": ["dimension", ["template-tag", "exclude_spending"]],
        "name": "Exclude Spending",
        "slug": "exclude_spending",
        "options": {"case-sensitive": False},
        "isMultiSelect": True,
        "values_query_type": "list",
    },
    "include_spending": {
        "type": "string/contains",
        "target": ["dimension", ["template-tag", "include_spending"]],
        "name": "Include Spending",
        "slug": "include_spending",
        "options": {"case-sensitive": False},
        "isMultiSelect": True,
        "values_query_type": "list",
    },
    "category": {
        "type": "string/=",
        "target": ["dimension", ["template-tag", "category"]],
        "name": "Category",
        "slug": "category",
        "isMultiSelect": True,
    },
    "frequency_bucket": {
        "slug": "frequency_bucket",
        "values_query_type": "list",
        "name": "Frequency Bucket",
        "isMultiSelect": True,
        "type": "string/=",
        "values_source_type": "static-list",
        "target": ["variable", ["template-tag", "frequency_bucket"]],
        "values_source_config": {"values": [["1"], ["2-3"], ["4-9"], ["10+"]]},
    },
}

# Define reusable template tag definitions
COMMON_TEMPLATE_TAGS = {
    "year_month": {
        "id": "year_month",
        "name": "year_month",
        "display-name": "Year Month",
        "type": "dimension",
        "widget-type": "string/=",
        "dimension": ["field", 74, None],
        "required": False,
    },
    "exclude_spending": {
        "id": "exclude_spending",
        "name": "exclude_spending",
        "display-name": "Exclude Spending",
        "type": "dimension",
        "widget-type": "string/contains",
        "dimension": ["field", 73, None],
        "required": False,
    },
    "include_spending": {
        "id": "include_spending",
        "name": "include_spending",
        "display-name": "Include Spending",
        "type": "dimension",
        "widget-type": "string/contains",
        "dimension": ["field", 73, None],
        "required": False,
    },
    "category": {
        "id": "category",
        "name": "category",
        "display-name": "Category",
        "type": "dimension",
        "widget-type": "string/=",
        "dimension": ["field", 75, None],
        "required": False,
    },
    "frequency_bucket": {
        "id": "frequency_bucket",
        "name": "frequency_bucket",
        "display-name": "Frequency Bucket",
        "type": "text",
        "required": False,
        "default": "1,2-3,4-9,10+",
    },
}

# Define reusable template tag sets
TEMPLATE_TAG_SETS = {
    "standard": {
        "year_month": COMMON_TEMPLATE_TAGS["year_month"],
        "exclude_spending": COMMON_TEMPLATE_TAGS["exclude_spending"],
        "include_spending": COMMON_TEMPLATE_TAGS["include_spending"],
        "category": COMMON_TEMPLATE_TAGS["category"],
    },
    "with_frequency": {
        "exclude_spending": COMMON_TEMPLATE_TAGS["exclude_spending"],
        "include_spending": COMMON_TEMPLATE_TAGS["include_spending"],
        "category": COMMON_TEMPLATE_TAGS["category"],
        "frequency_bucket": COMMON_TEMPLATE_TAGS["frequency_bucket"],
        "year_month": COMMON_TEMPLATE_TAGS["year_month"],
    },
}

# Define reusable parameter sets
PARAMETER_SETS = {
    "standard": [
        COMMON_PARAMETERS["year_month"],
        COMMON_PARAMETERS["exclude_spending"],
        COMMON_PARAMETERS["include_spending"],
        COMMON_PARAMETERS["category"],
    ],
    "with_frequency": [
        COMMON_PARAMETERS["exclude_spending"],
        COMMON_PARAMETERS["include_spending"],
        COMMON_PARAMETERS["category"],
        COMMON_PARAMETERS["frequency_bucket"],
        COMMON_PARAMETERS["year_month"],
    ],
}


class MetabaseDashboardCreator:
    def __init__(self, metabase_url, username, password, database_id=1):
        """Initialize the Metabase API connection."""
        self.mb = Metabase_API(metabase_url, username, password)
        self.database_id = database_id
        self.cards = {}
        self.dashboard_id = None

    def get_cards(self):
        """Retrieve existing cards from Metabase."""
        try:
            response = self.mb.get("/api/card")
            if response:
                for card in response:
                    self.cards[card["name"]] = card
                print(f"✓ Retrieved {len(self.cards)} existing cards")
            else:
                print("✗ Failed to retrieve cards")
        except Exception as e:
            print(f"✗ Error retrieving cards: {str(e)}")

    def get_dashboard_cards(self, dashboard_id):
        """Retrieve cards from a specific dashboard with their visualization settings."""
        try:
            response = self.mb.get(f"/api/dashboard/{dashboard_id}")
            if response and "dashcards" in response:
                dashboard_cards = {}
                for dashcard in response["dashcards"]:
                    if "card" in dashcard:
                        card = dashcard["card"]
                        card_name = card.get("name", "")
                        # Include visualization settings from the dashboard card
                        visualization_settings = dashcard.get("visualization_settings", {})
                        dashboard_cards[card_name] = {
                            "card_info": card,
                            "visualization_settings": visualization_settings,
                            "display": card.get("display", "table"),
                        }
                print(f"✓ Retrieved {len(dashboard_cards)} cards from dashboard {dashboard_id}")
                return dashboard_cards
            else:
                print(f"✗ Failed to retrieve cards from dashboard {dashboard_id}")
                return {}
        except Exception as e:
            print(f"✗ Error retrieving dashboard cards: {str(e)}")
            return {}

    def get_dashboard_layout(self, dashboard_id):
        """Retrieve complete dashboard layout information."""
        try:
            response = self.mb.get(f"/api/dashboard/{dashboard_id}")
            if response and "dashcards" in response:
                layout_info = {}
                for dashcard in response["dashcards"]:
                    if "card" in dashcard:
                        card_name = dashcard["card"].get("name", "")
                        layout_info[card_name] = {
                            "row": dashcard.get("row", 0),
                            "col": dashcard.get("col", 0),
                            "size_x": dashcard.get("size_x", 4),
                            "size_y": dashcard.get("size_y", 4),
                            "visualization_settings": dashcard.get("visualization_settings", {}),
                            "parameter_mappings": dashcard.get("parameter_mappings", []),
                        }
                print(f"✓ Retrieved layout for {len(layout_info)} cards from dashboard {dashboard_id}")
                return layout_info
            else:
                print(f"✗ Failed to retrieve cards from dashboard {dashboard_id}")
                return {}
        except Exception as e:
            print(f"✗ Error retrieving dashboard layout: {str(e)}")
            return {}

    def create_card(self, card_data):
        """Create a new card (question) in Metabase."""
        try:
            name = card_data.get("name", "Unknown Card")

            # Check if card already exists
            if name in self.cards:
                print(f"⏭️  Card already exists: {name} (ID: {self.cards[name]['id']})")
                print("   Skipping card creation...")
                return self.cards[name]

            # Generate unique IDs for parameters if provided
            parameters = card_data.get("parameters", [])
            if parameters:
                import uuid

                for param in parameters:
                    if "id" not in param:
                        param["id"] = str(uuid.uuid4())

            response = self.mb.post("/api/card", json=card_data)

            if response:
                card_info = response
                self.cards[name] = card_info
                param_count = len(parameters)
                print(f"✓ Created card: {name} (ID: {card_info['id']}) with {param_count} parameters")
                return card_info
            else:
                print(f"✗ Failed to create card {name}")
                return None
        except Exception as e:
            print(f"✗ Error creating card {name}: {str(e)}")
            return None

    def _build_card_data(self, config):
        """Build complete card_data from config."""
        return {
            "name": config["name"],
            "description": config.get("description", ""),
            "dataset_query": {
                "type": "native",
                "native": {"query": config["sql"], "template-tags": config.get("template_tags", {})},
                "database": self.database_id,
            },
            "display": config.get("display", "table"),
            "visualization_settings": config.get("visualization_settings", {}),
            "parameters": config.get("parameters", []),
        }

    def dashboard_exists(self, name, description):
        """Check if a dashboard with the same name and description already exists."""
        try:
            response = self.mb.get("/api/dashboard")
            if response:
                for dashboard in response:
                    if dashboard.get("name") == name and dashboard.get("description") == description:
                        return dashboard
            return None
        except Exception as e:
            print(f"✗ Error checking existing dashboards: {str(e)}")
            return None

    def create_dashboard(self, name="Financial Tracker Dashboard", description="Comprehensive financial tracking dashboard"):
        """Create a new dashboard."""
        try:
            # Check if dashboard already exists
            existing_dashboard = self.dashboard_exists(name, description)
            if existing_dashboard:
                self.dashboard_id = existing_dashboard["id"]
                print(f"⏭️  Dashboard already exists: {name} (ID: {self.dashboard_id})")
                print("   Skipping dashboard creation...")
                return existing_dashboard

            dashboard_data = {"name": name, "description": description}

            response = self.mb.post("/api/dashboard", json=dashboard_data)
            if response:
                dashboard_info = response
                self.dashboard_id = dashboard_info["id"]
                print(f"✓ Created dashboard: {name} (ID: {self.dashboard_id})")
                return dashboard_info
            else:
                print("✗ Failed to create dashboard")
                return None
        except Exception as e:
            print(f"✗ Error creating dashboard: {str(e)}")
            return None

    def add_cards_to_dashboard(self, cards_config, dashboard_parameters=None):
        """Add multiple cards to dashboard with their layout positions and parameter mappings."""
        if not self.dashboard_id:
            print("✗ No dashboard ID available")
            return False

        print(f"📌 Adding {len(cards_config)} cards to dashboard {self.dashboard_id} with filters...")

        try:
            import uuid

            # Get current dashboard
            current_dashboard = self.mb.get(f"/api/dashboard/{self.dashboard_id}")
            if not current_dashboard:
                print(f"✗ Could not retrieve dashboard {self.dashboard_id}")
                return False

            # Get existing card IDs in dashboard
            existing_dashcards = current_dashboard.get("dashcards", [])
            existing_card_ids = [dashcard.get("card_id") for dashcard in existing_dashcards if dashcard.get("card_id")]
            print(f"existing_card_ids: {existing_card_ids}")

            # Create dashboard-level parameters if not provided
            if dashboard_parameters is None:
                # Convert COMMON_PARAMETERS to dashboard format with unique IDs
                dashboard_parameters = []
                for param_def in COMMON_PARAMETERS.values():
                    dashboard_param = param_def.copy()
                    dashboard_param["id"] = str(uuid.uuid4())
                    dashboard_parameters.append(dashboard_param)

            # Build parameter mapping lookup by slug
            param_lookup = {param["slug"]: param["id"] for param in dashboard_parameters}

            # Build dashcards with parameter mappings
            new_dashcards = []
            for config in cards_config:
                card_name = config["name"]

                if card_name in self.cards:
                    card_id = self.cards[card_name]["id"]

                    # Check if card is already in dashboard
                    if card_id in existing_card_ids:
                        print(f"  ⏭️  Card already in dashboard: {card_name} (ID: {card_id})")
                        continue

                    # Build parameter mappings for this card
                    parameter_mappings = []
                    card_parameters = config.get("parameters", [])

                    for card_param in card_parameters:
                        param_slug = card_param.get("slug")
                        if param_slug and param_slug in param_lookup:
                            dashboard_param_id = param_lookup[param_slug]
                            mapping = {
                                "parameter_id": dashboard_param_id,
                                "card_id": card_id,
                                "target": card_param.get("target", ["dimension", ["template-tag", param_slug]]),
                            }
                            parameter_mappings.append(mapping)

                    # Create dashcard with layout and parameter mappings
                    dashcard_data = {
                        "id": card_id,
                        "card_id": card_id,
                        "row": config.get("row", 0),
                        "col": config.get("col", 0),
                        "size_x": config.get("size_x", 4),
                        "size_y": config.get("size_y", 4),
                        "parameter_mappings": parameter_mappings,
                        "visualization_settings": config.get("visualization_settings", {}),
                    }

                    new_dashcards.append(dashcard_data)
                    row, col = config.get("row", 0), config.get("col", 0)
                    print(f"  ✓ Prepared {card_id}: {card_name} at ({row}, {col}) with {len(parameter_mappings)} mappings")
                else:
                    print(f"  ⚠️  Card not found: {card_name}")

            # Update dashboard with dashcards and parameters
            all_dashcards = existing_dashcards + new_dashcards

            update_data = {"dashcards": all_dashcards, "parameters": dashboard_parameters, "database_id": self.database_id}

            print(f"  🔍 Updating dashboard with {len(all_dashcards)} dashcards and {len(dashboard_parameters)} parameters")

            response = self.mb.put(f"/api/dashboard/{self.dashboard_id}", json=update_data)

            if response is not None and response:
                print(f"✓ Updated dashboard {self.dashboard_id} with {len(new_dashcards)} new cards and filters")
                return True
            else:
                print("✗ Failed to update dashboard with cards and filters")
                return False

        except Exception as e:
            print(f"✗ Error adding cards to dashboard: {str(e)}")
            return False

    def delete_dashboard(self, dashboard_id):
        """Delete a dashboard by ID."""
        try:
            response = self.mb.delete(f"/api/dashboard/{dashboard_id}")
            if response is not None:  # DELETE requests may return None on success
                print(f"✓ Deleted dashboard ID: {dashboard_id}")
                return True
            else:
                print(f"✗ Failed to delete dashboard ID: {dashboard_id}")
                return False
        except Exception as e:
            print(f"✗ Error deleting dashboard {dashboard_id}: {str(e)}")
            return False

    def delete_dashboards(self, dashboard_ids):
        """Delete multiple dashboards by their IDs."""
        if not dashboard_ids:
            print("⚠️  No dashboard IDs provided")
            return []

        print(f"🗑️  Deleting {len(dashboard_ids)} dashboards...")
        results = []
        for dashboard_id in dashboard_ids:
            success = self.delete_dashboard(dashboard_id)
            results.append({"id": dashboard_id, "success": success})

        successful = sum(1 for r in results if r["success"])
        print(f"📊 Dashboard deletion complete: {successful}/{len(dashboard_ids)} successful")
        return results

    def delete_card(self, card_id):
        """Delete a card by ID."""
        try:
            response = self.mb.delete(f"/api/card/{card_id}")
            if response is not None:  # DELETE requests may return None on success
                print(f"✓ Deleted card ID: {card_id}")
                # Remove from local cards dict if it exists
                for name, card_info in list(self.cards.items()):
                    if card_info.get("id") == card_id:
                        del self.cards[name]
                        break
                return True
            else:
                print(f"✗ Failed to delete card ID: {card_id}")
                return False
        except Exception as e:
            print(f"✗ Error deleting card {card_id}: {str(e)}")
            return False

    def delete_cards(self, card_ids):
        """Delete multiple cards by their IDs."""
        if not card_ids:
            print("⚠️  No card IDs provided")
            return []

        print(f"🗑️  Deleting {len(card_ids)} cards...")
        results = []
        for card_id in card_ids:
            success = self.delete_card(card_id)
            results.append({"id": card_id, "success": success})

        successful = sum(1 for r in results if r["success"])
        print(f"📊 Card deletion complete: {successful}/{len(card_ids)} successful")
        return results


def main():
    """Main execution function."""
    print("🚀 Starting Metabase Dashboard Creation")
    print("=" * 50)

    # Configuration - Load from environment variables
    METABASE_URL = os.getenv("METABASE_URL", "http://localhost:3000")
    USERNAME = os.getenv("METABASE_USERNAME")
    PASSWORD = os.getenv("METABASE_PASSWORD")
    DATABASE_ID = int(os.getenv("METABASE_DATABASE_ID", "1"))

    # Validate required environment variables
    if not USERNAME:
        print("✗ METABASE_USERNAME environment variable is required")
        print("  Add METABASE_USERNAME=your_username to your .env file")
        return

    if not PASSWORD:
        print("✗ METABASE_PASSWORD environment variable is required")
        print("  Add METABASE_PASSWORD=your_password to your .env file")
        return

    print("✓ Configuration loaded from environment variables:")
    print(f"   METABASE_URL: {METABASE_URL}")
    print(f"   USERNAME: {USERNAME}")
    print(f"   DATABASE_ID: {DATABASE_ID}")
    print()

    # Initialize Metabase connection
    try:
        print("🔌 Connecting to Metabase...")
        creator = MetabaseDashboardCreator(METABASE_URL, USERNAME, PASSWORD, DATABASE_ID)
        print("✓ Connected to Metabase")
    except Exception as e:
        print(f"✗ Failed to connect to Metabase: {str(e)}")
        return

    # Get existing cards
    print("\n📋 Retrieving existing cards...")
    creator.get_cards()

    # Create cards
    print("\n📊 Creating cards...")

    card_configs = [
        {
            "name": "Total Spending YTD",
            "description": "Total spending year-to-date excluding payments",
            "display": "scalar",
            "visualization_settings": {"column_settings": {'["name","total_spending_ytd"]': {"number_style": "currency"}}},
            "parameters": PARAMETER_SETS["standard"],
            "template_tags": TEMPLATE_TAG_SETS["standard"],
            "row": 0,
            "col": 0,
            "size_x": 6,
            "size_y": 3,
            "sql": """SELECT
    SUM(amount) as total_spending_ytd
FROM financial_transactions
WHERE 1=1
    [[AND {{year_month}}]]
	[[AND not {{exclude_spending}}]]
	[[AND {{include_spending}}]]
	[[AND {{category}}]]
    AND category != 'Payment';""",
        },
        {
            "name": "Average Monthly Spending",
            "description": "Average monthly spending amount",
            "display": "scalar",
            "visualization_settings": {"column_settings": {}},
            "parameters": PARAMETER_SETS["standard"],
            "template_tags": TEMPLATE_TAG_SETS["standard"],
            "row": 0,
            "col": 6,
            "size_x": 6,
            "size_y": 3,
            "sql": """with total as (
SELECT
	year_month,
    SUM(amount) as total_spending
FROM financial_transactions
WHERE 1=1
    [[AND {{year_month}}]]
	[[AND not {{exclude_spending}}]]
	[[AND {{include_spending}}]]
	[[AND {{category}}]]
    AND category != 'Payment'
group by year_month	)
	select avg(total_spending) as avg_spending from total;""",
        },
        {
            "name": "Spending by Category",
            "description": "Distribution of spending across categories",
            "display": "pie",
            "visualization_settings": {
                "pie.dimension": ["category"],
                "pie.percent_visibility": "inside",
                "pie.show_labels": False,
                "pie.show_total": True,
                "pie.show_legend": True,
                "version": 2,
            },
            "parameters": PARAMETER_SETS["standard"],
            "template_tags": TEMPLATE_TAG_SETS["standard"],
            "row": 15,
            "col": 14,
            "size_x": 10,
            "size_y": 8,
            "sql": """SELECT
    category,
    SUM(amount) as total_amount
FROM financial_transactions
WHERE category != 'Payment'
    [[AND {{year_month}}]]
	[[AND not {{exclude_spending}}]]
	[[AND {{include_spending}}]]
	[[AND {{category}}]]
GROUP BY category
ORDER BY total_amount DESC;""",
        },
        {
            "name": "Monthly Spending Trends by Category",
            "description": "Monthly spending trends broken down by category",
            "display": "bar",
            "visualization_settings": {
                "graph.dimensions": ["year_month", "category"],
                "graph.series_order_dimension": None,
                "graph.series_order": None,
                "stackable.stack_type": "stacked",
                "graph.show_values": True,
                "graph.x_axis.scale": "timeseries",
                "graph.metrics": ["monthly_spending"],
            },
            "parameters": PARAMETER_SETS["standard"],
            "template_tags": TEMPLATE_TAG_SETS["standard"],
            "row": 3,
            "col": 0,
            "size_x": 24,
            "size_y": 12,
            "sql": """SELECT
    year_month,
    category,
    SUM(amount) as monthly_spending
FROM financial_transactions
WHERE category != 'Payment'
[[AND {{year_month}}]]
[[AND not {{exclude_spending}}]]
[[AND {{include_spending}}]]
[[AND {{category}}]]
GROUP BY year_month, category
ORDER BY year_month, monthly_spending DESC;""",
        },
        {
            "name": "Top 20 Merchants",
            "description": "Top 20 merchants by total spending amount",
            "display": "row",
            "visualization_settings": {
                "graph.show_goal": False,
                "graph.show_values": True,
                "graph.x_axis.labels_enabled": False,
                "graph.series_order_dimension": None,
                "graph.metrics": ["total_amount"],
                "graph.label_value_formatting": "full",
                "graph.series_order": None,
                "graph.dimensions": ["merchant_name", "category"],
                "stackable.stack_type": "stacked",
            },
            "parameters": PARAMETER_SETS["standard"],
            "template_tags": TEMPLATE_TAG_SETS["standard"],
            "row": 15,
            "col": 0,
            "size_x": 14,
            "size_y": 8,
            "sql": """SELECT
  description AS merchant_name,
  SUM(amount) AS total_amount,
  COUNT(*) AS transaction_count,
  category,
  ROUND(AVG(amount), 2) AS avg_amount
FROM
  financial_transactions
WHERE
  1 = 1 [[AND {{year_month}}]]
  [[AND not {{exclude_spending}}]]
  [[AND {{include_spending}}]]
  [[AND {{category}}]]
  AND category != 'Payment'
GROUP BY
  description,
  category
ORDER BY
  total_amount DESC
LIMIT
  20;""",
        },
        {
            "name": "Transaction Frequency Analysis",
            "description": "Analysis of transaction frequency patterns",
            "display": "table",
            "visualization_settings": {"table.pivot_column": "created_at", "table.cell_column": "amount"},
            "parameters": PARAMETER_SETS["with_frequency"],
            "template_tags": TEMPLATE_TAG_SETS["with_frequency"],
            "row": 23,
            "col": 0,
            "size_x": 14,
            "size_y": 8,
            "sql": """
WITH tx AS (
  SELECT
    *,
    COUNT(*) OVER (PARTITION BY description) AS frequency,
    CASE
      WHEN COUNT(*) OVER (PARTITION BY description) = 1 THEN '1'
      WHEN COUNT(*) OVER (PARTITION BY description) BETWEEN 2 AND 3 THEN '2-3'
      WHEN COUNT(*) OVER (PARTITION BY description) BETWEEN 4 AND 9 THEN '4-9'
      ELSE '10+'
    END AS frequency_bucket
  FROM financial_transactions
  WHERE 1=1
  	AND category != 'Payment'
    [[AND {{year_month}}]]
    [[AND NOT {{exclude_spending}}]]
    [[AND {{include_spending}}]]
    [[AND {{category}}]]
)
SELECT transaction_date, raw_description, amount, category, frequency
FROM tx
WHERE 1=1
  [[AND frequency_bucket in ({{frequency_bucket}})]]
ORDER BY frequency desc, description, transaction_date LIMIT 100;""",
        },
    ]

    for config in card_configs:
        card_data = creator._build_card_data(config)
        creator.create_card(card_data)

    # Create dashboard
    print("\n🏗️  Creating dashboard...")
    dashboard = creator.create_dashboard()

    if not dashboard:
        print("✗ Failed to create dashboard. Exiting.")
        return

    # Add cards to dashboard with filters and parameter mappings
    result = creator.add_cards_to_dashboard(card_configs)

    if result:
        print("\n🎉 Dashboard creation completed!")
        print(f"🔗 Dashboard URL: {METABASE_URL}/dashboard/{creator.dashboard_id}")

        # Summary
        print("\n📋 Summary:")
        print(f"   • Created {len(creator.cards)} cards")
        print(f"   • Created 1 dashboard with ID: {creator.dashboard_id}")
        print("   • Added cards with filters and parameter mappings")
        print("\n⚡ Your financial tracking dashboard is ready!")
    else:
        print("\n✗ Failed to add cards to dashboard")
        print(f"🔗 Dashboard URL: {METABASE_URL}/dashboard/{creator.dashboard_id}")
        print("\n📋 Summary:")
        print(f"   • Created {len(creator.cards)} cards")
        print(f"   • Created 1 dashboard with ID: {creator.dashboard_id}")
        print("   • ⚠️  Cards could not be added automatically")


if __name__ == "__main__":
    main()
