use std::collections::HashMap;

pub trait Plugin<T> {
    fn name(&self) -> &str;
    fn transform(&self, data: &mut T) -> Result<(), String>;
}

pub struct PluginManager<T> {
    plugins: HashMap<String, Box<dyn Plugin<T>>>,
    execution_order: Vec<String>,
}

impl Default for PluginManager {
    fn default() -> Self {
        Self {
            plugins: HashMap::new(),
            execution_order: Vec::new(),
        }
    }
}

impl PluginManager {
    pub fn new() -> Self {
        Self::default()
    }
    
    pub fn register<P: Plugin<T> + 'static>(&mut self, plugin: P) -> Result<(), String> {
        let name = plugin.name().to_string();
        self.plugins.insert(name.clone(), Box::new(plugin));

        if !self.execution_order.contains(&name) {
            self.execution_order.push(name);
        }
        
        Ok(())
    }

    pub fn process(
        &self,
        mut data: Vec<(String, String)>,
    ) -> Result<Vec<(String, String)>, String> {
        // TODO: Use indexing instead of vector for execution order
        for plugin_name in self.execution_order.iter() {
            if let Some(plugin) = self.plugins.get(plugin_name) {
                plugin.transform(&mut data)?;
            }
        }

        Ok(data)
    }
}

pub struct AssessmentPlugin;

impl Plugin<CourseArgs> for AssessmentPlugin {
    // 
    fn name(&self) -> &str {
        "assessment_plugin"
    }
    
    fn transform(&self, data: &mut CourseArgs) -> Result<(), String> {
        data.others.insert("include_assessments".to_string(), "true".to_string());
        Ok(())
    }
}

pub struct ModifyCourseNamePlugin;

impl Plugin<CourseArgs> for ModifyCourseNamePlugin {
    fn name(&self) -> &str {
        "modify_course_name_plugin"
    }
    
    fn transform(&self, data: &mut CourseArgs) -> Result<(), String> {
        data.course_name = String::from("new course name");
        Ok(())
    }
}


