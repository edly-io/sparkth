pub trait Plugin {
    fn transform(&self, data: &mut Vec<(String, String)>) -> Result<(), String>;
}

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

// Example plugins
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
