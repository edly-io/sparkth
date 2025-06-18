// use std::collections::HashMap;

// #[derive(Debug, Clone)]
// pub struct PromptArgument {
//     pub name: String,
//     pub description: String,
//     pub required: bool,
// }

// #[derive(Debug, Clone)]
// pub struct PromptTemplate {
//     pub name: String,
//     pub description: String,
//     pub arguments: Vec<PromptArgument>,
//     pub template: String,
// }

// fn get_course_creation_prompt() -> PromptTemplate {
//     PromptTemplate {
//         name: "Course Creation".to_string(),
//         description: "Generate a comprehensive course structure following instructional design principles including learning objectives, content organization, and assessment strategies.".to_string(),
//         arguments: vec![
//             PromptArgument {
//                 name: "course_name".to_string(),
//                 description: "The name of the course.".to_string(),
//                 required: true,
//             },
//             PromptArgument {
//                 name: "course_description".to_string(),
//                 description: "A brief description of the course.".to_string(),
//                 required: true,
//             },
//             PromptArgument {
//                 name: "course_target_audience".to_string(),
//                 description: "Description of the target learners (e.g., 'beginners', 'professionals')".to_string(),
//                 required: false,
//             },
//             PromptArgument {
//                 name: "course_duration".to_string(),
//                 description: "The expected duration of the course in days or weeks.".to_string(),
//                 required: false,
//             },
//         ],
//         template: r#"Create a short, {{course_duration}} long introduction course on {{course_description}} with the name {{course_name}}.
//         This course is intended for {{course_target_audience}}. Course may be composed of text, images and videos (which you can find on the web). The course structure should follow proven instructional design principles. Organize the course into logical sections, each containing:
//         - Section title and learning outcomes
//         - The subsections with detailed content
//         - Verticals for the subsections
//         - Units for each vertical
//         - Estimated time commitment
//         - Prerequisites (if any)
//         Design a comprehensive assessment plan; assessments will include multiple-choice questions, free-form text and short project assignments.
//          "#.to_string(),
//     }
// }

pub fn get_course_generation_prompt(course_name: &str, course_duration: &str, course_description: &str) -> String {
    format!(r"Generate the content of an online course titled '{course_name}'. The expected duration will be {course_duration}.

{course_description}

Generate the content by using good learning design principles. In particular, the course should include short, engaging learning units.

Create the course using simple text elements and links to external resources such as images, videos or documents. Do not generate assessments or interactive elements for now. This course is meant to be taken online, so avoid any group activity.

Generate the course in the language used by the user.

Make sure to fill the actual course content, and not just the outline.")
}

#[cfg(test)]
mod tests {
    use crate::prompts::get_course_generation_prompt;

    #[test]
    fn test_get_course_generation_prompt() {
        // presence of empty strings in the prompt
        // hashmap is not a good choice for this
        // (key, value) pair in vector
        // have to correctly format thhe arguments in proper english
        // have a list of defined arguments and enforce them
        // let mut args = HashMap::new();
        // args.insert("course_duration".to_string(), "3 weeks".to_string());

        let prompt = get_course_generation_prompt("My Course", "3 weeks", "This is a course about Rust programming.");
        assert!(!prompt.is_empty());


        // dbg!(&prompt);
        // assert!(!prompt.contains("\t"));
        // assert!(prompt.contains("3 weeks"));
    }
}
