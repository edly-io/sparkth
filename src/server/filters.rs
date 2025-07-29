use crate::{define_filter_chain, server::types::CoursePayload};

// TODO: Create filters for plugins 
// Add the filters to the plugin context

define_filter_chain!(
    CoursePayloadFilterChain,
    fn(&mut CoursePayload, username: &str)
);

#[derive(Default)]
pub struct Filters {
    pub _course_filter_chain: CoursePayloadFilterChain,
}
