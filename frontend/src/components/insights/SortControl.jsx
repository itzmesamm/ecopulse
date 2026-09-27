export default function SortControl({ priority, resourceType, savingsOrder, resourceTypes, onChange }) {
  return (
    <div className="sort-bar">
      <div className="filter-heading">Filters</div>
      <div className="filter-field">
        <label className="sort-label" htmlFor="recommendation-priority">Priority</label>
        <select
          id="recommendation-priority"
          className="sort-select"
          value={priority}
          onChange={(event) => onChange({ priority: event.target.value })}
        >
          <option value="all">All priorities</option>
          <option value="high">High priority</option>
          <option value="medium">Medium priority</option>
          <option value="low">Low priority</option>
        </select>
      </div>

      <div className="filter-field">
        <label className="sort-label" htmlFor="recommendation-resource-type">Resource type</label>
        <select
          id="recommendation-resource-type"
          className="sort-select"
          value={resourceType}
          onChange={(event) => onChange({ resourceType: event.target.value })}
        >
          <option value="all">All resource types</option>
          {resourceTypes.map((type) => (
            <option key={type} value={type}>{type}</option>
          ))}
        </select>
      </div>

      <div className="filter-field">
        <label className="sort-label" htmlFor="recommendation-savings">Savings</label>
        <select
          id="recommendation-savings"
          className="sort-select"
          value={savingsOrder}
          onChange={(event) => onChange({ savingsOrder: event.target.value })}
        >
          <option value="highest">Highest savings</option>
          <option value="lowest">Lowest savings</option>
        </select>
      </div>
    </div>
  );
}