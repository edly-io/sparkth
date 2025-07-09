use crate::{canvas::client::Course, define_filter_chain, mcp_server::CourseGenerationPromptRequest};

define_filter_chain!(CoursePromptFilterChain, fn(&mut CourseGenerationPromptRequest));
define_filter_chain!(CourseFilterChain, fn(&mut Vec<Course>));