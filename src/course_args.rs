use std::{collections::HashMap};

pub trait Plugin<T> {
    fn transform(&self, data: &mut T) -> Result<(), String>;
}

pub struct PluginManager<T> {
    plugins: Vec<Box<dyn Plugin<T>>>,
}

impl<T> Default for PluginManager<T> {
    fn default() -> Self {
        Self {
            plugins: Vec::new(),
        }
    }
}

impl<T> PluginManager<T> {
    pub fn new() -> Self {
        Self::default()
    }
    
    pub fn register<P: Plugin<T> + 'static>(&mut self, plugin: P) -> Result<(), String> {
        self.plugins.push(Box::new(plugin));
        
        Ok(())
    }
    
    pub fn process(&self, mut data: T) -> Result<T, String> {
        // TODO: Use indexing instead of vector for execution order
        for plugin in self.plugins.iter() {
            plugin.transform(&mut data)?;
        }
        
        Ok(data)
    }
}

#[derive(Debug, Clone)]
pub struct CourseArgs {
    pub course_duration: String,
    pub course_name: String,
    pub course_description: String,
    pub others: HashMap<String, String>,
}

pub struct AssessmentPlugin;

impl Plugin<CourseArgs> for AssessmentPlugin {
    fn transform(&self, data: &mut CourseArgs) -> Result<(), String> {
        data.others.insert("include_assessments".to_string(), "true".to_string());
        Ok(())
    }
}

pub struct ModifyCourseNamePlugin;

impl Plugin<CourseArgs> for ModifyCourseNamePlugin {
    fn transform(&self, data: &mut CourseArgs) -> Result<(), String> {
        data.course_name = String::from("new course name");
        Ok(())
    }
}
