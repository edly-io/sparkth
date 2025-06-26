/// Creates a filter chain structure that can hold and execute multiple filters in sequence.
/// All filters must conform to the specified function signature and will be executed
/// in the order they were added.
///
/// # Syntax
///
/// ```
/// define_filter_chain!(StructName, fn(&mut DataType));
/// define_filter_chain!(StructName, fn(&mut DataType, arg1: Type1, /* add more arguments if required */));
/// ```
/// Note: The first parameter of the filter signature must always be `&mut T` where T is your data type
///
///
/// # Generated Methods
/// The macro generates a struct with the following methods:
/// - `new()` - Creates a new empty filter chain
/// - `add_filter(filter)` - Adds a filter function or closure to the chain
/// - `process(data, ...)` - Applies all filters in sequence to the provided data
/// - `filter_count()` - Returns the number of filters in the chain
///
///
/// # Examples
///
/// ## Basic usage with mutable data only
///
/// ```
/// define_filter_chain!(FilterChain, fn(&mut Vec<String>));
///
/// let mut items = vec!["hello".to_string(), "world".to_string()];
///
/// let mut chain = FilterChain::new();
///
/// // add a filter that adds a new item
/// chain.add_filter(|items: &mut Vec<String>| {
///     items.push("new item".to_string());
/// });
///
/// // add a filter that converts to uppercase
/// chain.add_filter(|items: &mut Vec<String>| {
///     for item in items {
///         *item = item.to_uppercase();
///     }
/// });
///
/// chain.process(&mut items);   
///
/// assert_eq!(chain.filter_count(), 2);
/// assert_eq!(items, vec!["HELLO", "WORLD", "NEW ITEM"]);
///
/// ```
#[macro_export]
macro_rules! define_filter_chain {

    ($struct_name:ident, fn(&mut $data_type:ty $(, $arg_name:ident: $arg_type:ty)*)) => {
        pub struct $struct_name {
            filters: Vec<Box<dyn Fn(&mut $data_type, $($arg_type),*)>>,
        }

        impl $struct_name {
            pub fn new() -> Self {
                Self {
                    filters: Vec::new(),
                }
            }

            pub fn add_filter<F>(&mut self, filter: F) -> &mut Self
            where
                F: Fn(&mut $data_type, $($arg_type),*) + 'static,
            {
                self.filters.push(Box::new(filter));
                self
            }

            pub fn process(&self, data: &mut $data_type, $($arg_name: $arg_type),*) {
                for filter in &self.filters {
                    filter(data, $($arg_name),*);
                }
            }

            pub fn get_filter_count(&self) -> usize {
                self.filters.len()
            }
        }
    };
}

#[cfg(test)]
mod tests {

    define_filter_chain!(FilterChain, fn(&mut Vec<String>));
    define_filter_chain!(
        FilterChainWithUsername,
        fn(&mut Vec<(String, String)>, username: &str)
    );
    define_filter_chain!(
        FilterChainWithAdditionalArgs,
        fn(&mut Vec<(String, String)>, username: &str, age: f32)
    );

    #[test]
    fn test_simple_filter_chain() {
        let mut items = vec!["hello".to_string(), "world".to_string()];

        let mut chain = FilterChain::new();

        chain.add_filter(|items: &mut Vec<String>| {
            items.push("new item".to_string());
        });

        chain.add_filter(|items: &mut Vec<String>| {
            for item in items {
                *item = item.to_uppercase();
            }
        });

        chain.process(&mut items);

        assert_eq!(chain.get_filter_count(), 2);
        assert_eq!(items, vec!["HELLO", "WORLD", "NEW ITEM"]);
    }

    #[test]
    fn test_filter_chain_with_username() {
        let mut args = vec![
            ("course_name".to_string(), "abc".to_string()),
            ("course_duration".to_string(), "1 hour".to_string()),
        ];

        let filter_add_arg = |data: &mut Vec<(String, String)>, username: &str| {
            data.push(("include_assessments".to_string(), "true".to_string()));
            println!("Filter executed for user: {}", username);
        };

        let filter_modify_arg = |data: &mut Vec<(String, String)>, username: &str| {
            data[1].1 = "modified".to_string();
            println!("Filter executed for user: {}", username);
        };

        let mut chain = FilterChainWithUsername::new();
        chain
            .add_filter(filter_add_arg)
            .add_filter(filter_modify_arg);

        assert_eq!(chain.get_filter_count(), 2);

        chain.process(&mut args, "test_user");
        assert_eq!(
            args,
            vec![
                ("course_name".to_string(), "abc".to_string()),
                ("course_duration".to_string(), "modified".to_string()),
                ("include_assessments".to_string(), "true".to_string()),
            ]
        );
    }
}
