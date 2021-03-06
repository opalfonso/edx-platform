"""
Unit tests for getting the list of courses and the course outline.
"""
import json
import lxml
from django.core.urlresolvers import reverse

from contentstore.tests.utils import CourseTestCase
from xmodule.modulestore.django import loc_mapper
from xmodule.modulestore.tests.factories import CourseFactory
from xmodule.modulestore import parsers

class TestCourseIndex(CourseTestCase):
    """
    Unit tests for getting the list of courses and the course outline.
    """
    def setUp(self):
        """
        Add a course with odd characters in the fields
        """
        super(TestCourseIndex, self).setUp()
        # had a problem where index showed course but has_access failed to retrieve it for non-staff
        self.odd_course = CourseFactory.create(
            org='test.org_1-2',
            number='test-2.3_course',
            display_name='dotted.course.name-2',
        )


    def check_index_and_outline(self, authed_client):
        """
        Test getting the list of courses and then pulling up their outlines
        """
        index_url = '/course'
        index_response = authed_client.get(index_url, {}, HTTP_ACCEPT='text/html')
        parsed_html = lxml.html.fromstring(index_response.content)
        course_link_eles = parsed_html.find_class('course-link')
        self.assertGreaterEqual(len(course_link_eles), 2)
        for link in course_link_eles:
            self.assertRegexpMatches(
                link.get("href"),
                r'course/{0}+/branch/{0}+/block/{0}+'.format(parsers.ALLOWED_ID_CHARS)
            )
            # now test that url
            outline_response = authed_client.get(link.get("href"), {}, HTTP_ACCEPT='text/html')
            # ensure it has the expected 2 self referential links
            outline_parsed = lxml.html.fromstring(outline_response.content)
            outline_link = outline_parsed.find_class('course-link')[0]
            self.assertEqual(outline_link.get("href"), link.get("href"))
            course_menu_link = outline_parsed.find_class('nav-course-courseware-outline')[0]
            self.assertEqual(course_menu_link.find("a").get("href"), link.get("href"))

    def test_is_staff_access(self):
        """
        Test that people with is_staff see the courses and can navigate into them
        """
        self.check_index_and_outline(self.client)

    def test_negative_conditions(self):
        """
        Test the error conditions for the access
        """
        locator = loc_mapper().translate_location(self.course.location.course_id, self.course.location, False, True)
        outline_url = locator.url_reverse('course/', '')
        # register a non-staff member and try to delete the course branch
        non_staff_client, _ = self.createNonStaffAuthedUserClient()
        response = non_staff_client.delete(outline_url, {}, HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 403)

    def test_course_staff_access(self):
        """
        Make and register an course_staff and ensure they can access the courses
        """
        course_staff_client, course_staff = self.createNonStaffAuthedUserClient()
        for course in [self.course, self.odd_course]:
            new_location = loc_mapper().translate_location(course.location.course_id, course.location, False, True)
            permission_url = new_location.url_reverse("course_team/", course_staff.email)

            self.client.post(
                permission_url,
                data=json.dumps({"role": "staff"}),
                content_type="application/json",
                HTTP_ACCEPT="application/json",
            )

        # test access
        self.check_index_and_outline(course_staff_client)
