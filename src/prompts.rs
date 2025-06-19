pub fn get_course_generation_prompt(
    course_name: &str,
    course_duration: &str,
    course_description: &str,
) -> String {
    format!(
        r"Generate the content of an online course titled '{course_name}'. The expected duration will be {course_duration}.

{course_description}

Generate the content by using good learning design principles. In particular, the course should include short, engaging learning units.

Create the course using simple text elements and links to external resources such as images, videos or documents. Do not generate assessments or interactive elements for now. This course is meant to be taken online, so avoid any group activity.

Generate the course in the language used by the user.

Make sure to fill the actual course content, and not just the outline."
    )
}

#[cfg(test)]
mod tests {
    use crate::prompts::get_course_generation_prompt;

    #[test]
    fn test_get_course_generation_prompt() {
        let prompt = get_course_generation_prompt(
            "My Course",
            "3 weeks",
            "This is a course about Rust programming.",
        );
        assert!(!prompt.is_empty());
    }
}
