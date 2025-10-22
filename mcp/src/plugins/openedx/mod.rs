pub mod client;
pub mod types;

use crate::define_plugin;

define_plugin! {
    id: "openedx_lms",
    name: "Open edX",
    description: "Open edX Learning Management System integration with course creation and content management",
    type: Lms,
    router: openedx_tools_router
}
