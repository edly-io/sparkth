# Publish to your LMS

Sparkth builds courses in your LMS. LMS plugins have no page of their own:

1. Turn on your LMS's plugin in [Settings](plugins.md) and configure it with the details
   listed for it below.
2. In **Create Course**, ask the assistant to create the course there, for example
   "create this course in my LMS".

!!! note
    Sparkth checks that the URLs look right when you save, but not that your credentials work.
    A wrong URL, key or password shows up as an error when the assistant tries to create the
    course.

Each LMS decides differently when students can see what the assistant creates, so check its
section below before you start.

## Supported LMSes

As of the latest release, Sparkth supports these LMSes.

### Canvas

- The Canvas API URL of your institution.
- A Canvas API key (an access token from your Canvas account settings).

When students see it: the course is created unpublished. It stays hidden unless you ask the
assistant to make it visible to students.

### Open edX

- The Open edX LMS URL and the Open edX Studio URL.
- The username and password of your account on that Open edX instance.

When students see it: everything is a draft, hidden from learners, until you ask the assistant
to publish it.

### Moodle

- The Moodle API URL of your site.
- A Moodle API key (a web service token from your Moodle administrator).

!!! warning "Moodle has no draft"
    Anything the assistant creates in Moodle is visible to enrolled users immediately. While you
    are still shaping a course, work in a Moodle course that has no students.
