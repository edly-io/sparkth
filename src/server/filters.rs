use crate::{define_filter_chain, server::types::CreateCourseRequest};

define_filter_chain!(
    CoursePayloadFilterChain,
    fn(&mut CreateCourseRequest, username: &str)
);

#[derive(Default)]
pub struct Filters {
    pub course_filter_chain: CoursePayloadFilterChain,
}
