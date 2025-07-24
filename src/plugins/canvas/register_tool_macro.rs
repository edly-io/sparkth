#[macro_export]
macro_rules! register_tools {
    ($context:expr, $client:expr, [$( $tool:ident ),* $(,)?]) => {
        $(
            $context.tools.register($tool {
                canvas_client: $client.clone(),
            });
        )*
    };
}
