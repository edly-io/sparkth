/// A trait for implementing data transformation plugins.
///
/// Plugins can modify key-value pair data in place by implementing the `transform` method.
/// This allows for a flexible plugin system where different transformations can be applied
/// to data in a composable manner.
///
/// # Examples
///
/// ```
/// use your_crate::Plugin;
///
/// struct ExamplePlugin;
///
/// impl Plugin for ExamplePlugin {
///     fn transform(&self, data: &mut Vec<(String, String)>) -> Result<(), String> {
///         data.push(("example_key".to_string(), "example_value".to_string()));
///         Ok(())
///     }
/// }
/// ```
pub trait Plugin {
    /// Transforms the provided data in place.
    ///
    /// # Arguments
    ///
    /// * `data` - A mutable reference to a vector of key-value string pairs to be transformed
    ///
    /// # Returns
    ///
    /// * `Ok(())` if the transformation was successful
    /// * `Err(String)` if an error occurred during transformation, with an error message
    ///
    /// # Errors
    ///
    /// This method should return an error if the transformation cannot be completed
    /// for any reason, such as invalid data format or missing required fields.
    fn transform(&self, data: &mut Vec<(String, String)>) -> Result<(), String>;
}

/// Manages a collection of plugins and applies them to data sequentially.
///
/// The `PluginManager` provides a way to register multiple plugins and process data
/// through all of them in the order they were registered. If any plugin fails,
/// the entire processing stops and returns an error.
///
/// # Examples
///
/// ```
/// pub struct AssessmentPlugin;
///
/// impl Plugin for AssessmentPlugin {
///    fn transform(&self, data: &mut Vec<(String, String)>) -> Result<(), String> {
///        data.push(("include_assessments".to_string(), "true".to_string()));
///        Ok(())
///    }
/// }
///
/// pub struct ModifyCourseNamePlugin;
///
/// impl Plugin for ModifyCourseNamePlugin {
///    fn transform(&self, data: &mut Vec<(String, String)>) -> Result<(), String> {
///        let val = data.iter().position(|(key, _)| key == "course_name");
///        if let Some(index) = val {
///            data[index].1 = String::from("Modified Course Name");
///        }
///        Ok(())
///    }
/// }
///
/// let mut data: Vec<(String, String)> = vec![
///     ("course_name".to_string(), "abc".to_string()),
///     ("course_duration".to_string(), "1 hour".to_string()),
/// ];
///
/// let mut manager = PluginManager::new();
/// manager.register(AssessmentPlugin).unwrap();
/// manager.register(ModifyCourseNamePlugin).unwrap();
/// let result = manager.process(data).unwrap();
///
/// assert_eq!(data, vec![
///    ("course_name".to_string(), "Modified Course Name".to_string()),
///    ("course_duration".to_string(), "1 hour".to_string()),
///    ("include_assessments".to_string(), "true".to_string()),
/// ]);
///
/// ```
pub struct PluginManager {
    plugins: Vec<Box<dyn Plugin>>,
}

impl Default for PluginManager {
    fn default() -> Self {
        Self {
            plugins: Vec::new(),
        }
    }
}

impl PluginManager {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn register<P: Plugin + 'static>(&mut self, plugin: P) -> Result<(), String> {
        self.plugins.push(Box::new(plugin));

        Ok(())
    }

    pub fn process(
        &self,
        mut data: Vec<(String, String)>,
    ) -> Result<Vec<(String, String)>, String> {
        for plugin in self.plugins.iter() {
            plugin.transform(&mut data)?;
        }

        Ok(data)
    }
}

#[cfg(test)]
mod tests {
    use crate::plugins::plugin_system::{Plugin, PluginManager};

    pub struct AssessmentPlugin;

    impl Plugin for AssessmentPlugin {
        fn transform(&self, data: &mut Vec<(String, String)>) -> Result<(), String> {
            data.push(("include_assessments".to_string(), "true".to_string()));
            Ok(())
        }
    }

    pub struct ModifyCourseNamePlugin;

    impl Plugin for ModifyCourseNamePlugin {
        fn transform(&self, data: &mut Vec<(String, String)>) -> Result<(), String> {
            let val = data.iter().position(|(key, _)| key == "course_name");
            if let Some(index) = val {
                data[index].1 = String::from("Modified Course Name");
            }
            Ok(())
        }
    }

    #[test]
    fn test_include_assessment_plugin() {
        let data: Vec<(String, String)> = vec![
            ("course_name".to_string(), "abc".to_string()),
            ("course_duration".to_string(), "1 hour".to_string()),
        ];

        let mut manager = PluginManager::new();
        manager.register(AssessmentPlugin).unwrap();
        let result = manager.process(data).unwrap();

        assert_eq!(
            result,
            vec![
                ("course_name".to_string(), "abc".to_string()),
                ("course_duration".to_string(), "1 hour".to_string()),
                ("include_assessments".to_string(), "true".to_string()),
            ]
        );
    }

    #[test]
    fn test_modify_course_name_plugin() {
        let data: Vec<(String, String)> = vec![
            ("course_name".to_string(), "abc".to_string()),
            ("course_duration".to_string(), "1 hour".to_string()),
        ];

        let mut manager = PluginManager::new();
        manager.register(ModifyCourseNamePlugin).unwrap();
        let result = manager.process(data).unwrap();

        assert_eq!(
            result,
            vec![
                (
                    "course_name".to_string(),
                    "Modified Course Name".to_string()
                ),
                ("course_duration".to_string(), "1 hour".to_string()),
            ]
        );
    }
}
