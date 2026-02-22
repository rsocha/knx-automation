import StatusWidgets from "@/components/StatusWidgets";
import GroupAddressTable from "@/components/GroupAddressTable";

const Index = () => {
  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">
      <StatusWidgets />
      <GroupAddressTable />
    </div>
  );
};

export default Index;
