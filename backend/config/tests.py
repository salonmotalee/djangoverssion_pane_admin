"""The Django server guides browser users to the separate Next.js frontend."""

from django.test import SimpleTestCase, override_settings


@override_settings(FRONTEND_URL="http://127.0.0.1:3000/")
class FrontendEntryTests(SimpleTestCase):
    def test_browser_get_redirects_to_frontend_without_forwarding_query(self):
        response = self.client.get("/?next=https://untrusted.example/")
        self.assertRedirects(response, "http://127.0.0.1:3000/", fetch_redirect_response=False)
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_head_uses_same_destination_without_response_body(self):
        response = self.client.head("/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "http://127.0.0.1:3000/")
        self.assertEqual(response.content, b"")

    @override_settings(FRONTEND_URL="https://admin.example.com/workspace/")
    def test_production_frontend_destination_is_configurable(self):
        self.assertRedirects(
            self.client.get("/"),
            "https://admin.example.com/workspace/",
            fetch_redirect_response=False,
        )

    def test_entry_point_does_not_redirect_unsafe_methods(self):
        self.assertEqual(self.client.post("/").status_code, 405)
