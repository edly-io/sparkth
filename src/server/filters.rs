use crate::{define_filter_chain, server::types::CoursePayload};

define_filter_chain!(
    CoursePayloadFilterChain,
    fn(&mut CoursePayload, username: &str)
);

#[derive(Default)]
pub struct Filters {
    pub course_filter_chain: CoursePayloadFilterChain,
}
