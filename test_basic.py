import os
import unittest
from bs4 import BeautifulSoup
from app import create_app, db
from app.models import User, Role, Project
from app.services.scraper.static_scraper import StaticScraper

class WebScrapeProTestCase(unittest.TestCase):
    """Basic test suite for WebScrape Pro platform."""

    def setUp(self):
        """Sets up testing application database environment."""
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()

    def tearDown(self):
        """Cleans up database and context after runs."""
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_app_initialization(self):
        """Verify app runs in testing environment state."""
        self.assertTrue(self.app.config['TESTING'])
        self.assertFalse(self.app.config['DEBUG'])

    def test_database_seeding(self):
        """Verify default Roles are seeded correctly."""
        admin_role = Role.query.filter_by(name='Administrator').first()
        member_role = Role.query.filter_by(name='Member').first()
        
        self.assertIsNotNone(admin_role)
        self.assertIsNotNone(member_role)
        
        # Verify default seeded admin
        admin_user = User.query.filter_by(username='admin').first()
        self.assertIsNotNone(admin_user)
        self.assertTrue(admin_user.check_password('AdminPass123!'))

    def test_project_model_creation(self):
        """Verify projects can be successfully added to DB."""
        member = User.query.filter_by(username='admin').first()
        
        project = Project(
            name="Test Crawler 101",
            description="Testing project creations",
            user_id=member.id
        )
        db.session.add(project)
        db.session.commit()
        
        queried_proj = Project.query.filter_by(name="Test Crawler 101").first()
        self.assertIsNotNone(queried_proj)
        self.assertEqual(queried_proj.description, "Testing project creations")

    def test_offline_html_parser(self):
        """Isolate and test scraping parser logic offline using dummy HTML inputs."""
        mock_html = """
        <html>
            <head>
                <title>Mock Sandbox Shop</title>
                <meta name="description" content="Shop meta details description.">
            </head>
            <body>
                <h1>Welcome to Sandbox</h1>
                <p class="desc">This is a paragraph description.</p>
                <a href="https://example.com/item1">Item 1</a>
                <table>
                    <tr><th>Header A</th><th>Header B</th></tr>
                    <tr><td>Val 1</td><td>Val 2</td></tr>
                </table>
                <img src="/media/logo.png" alt="Company Logo">
                <span class="contacts">Support: support@sandbox.com Phone: 555-123-4567</span>
            </body>
        </html>
        """
        
        scraper = StaticScraper({"ignore_robots_txt": True})
        soup = BeautifulSoup(mock_html, 'html.parser')
        
        # Call parser directly
        extracted = scraper._extract_content(soup, "https://mocktarget.com")
        
        # Verify metadata
        self.assertEqual(extracted['meta']['title'], "Mock Sandbox Shop")
        self.assertEqual(extracted['meta']['description'], "Shop meta details description.")
        
        # Verify headings
        self.assertIn("Welcome to Sandbox", extracted['headings']['h1'])
        
        # Verify text
        self.assertIn("This is a paragraph description.", extracted['paragraphs'])
        
        # Verify links
        self.assertEqual(len(extracted['links']), 1)
        self.assertEqual(extracted['links'][0]['url'], "https://example.com/item1")
        
        # Verify contact regex
        self.assertIn("support@sandbox.com", extracted['contacts']['emails'])
        self.assertIn("555-123-4567", extracted['contacts']['phones'])
        
        # Verify tables
        self.assertEqual(len(extracted['tables']), 1)
        self.assertEqual(extracted['tables'][0]['headers'], ["Header A", "Header B"])
        self.assertEqual(extracted['tables'][0]['rows'][0]['Header A'], "Val 1")
        
        # Verify images
        self.assertEqual(len(extracted['media']['images']), 1)
        self.assertEqual(extracted['media']['images'][0]['url'], "https://mocktarget.com/media/logo.png")

if __name__ == '__main__':
    unittest.main()
