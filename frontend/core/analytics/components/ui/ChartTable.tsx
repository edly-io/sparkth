/**
 * Screen-reader copy of a chart's data. Charts hide their visuals and render one of these,
 * so assistive tech reads the numbers rather than a picture. A `className` shows it instead.
 */
export function ChartTable({
  caption,
  headers,
  rows,
  className = "sr-only",
}: {
  caption: string;
  headers: string[];
  rows: (string | number)[][];
  className?: string;
}) {
  return (
    <table className={className}>
      <caption>{caption}</caption>
      <thead>
        <tr>
          {headers.map((h, i) => (
            <th key={i} scope="col">
              {h}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, i) => (
          <tr key={i}>
            {row.map((cell, j) =>
              j === 0 ? (
                <th key={j} scope="row">
                  {cell}
                </th>
              ) : (
                <td key={j}>{cell}</td>
              ),
            )}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
