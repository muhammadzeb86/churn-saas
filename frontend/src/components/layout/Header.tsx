import React, { useState } from 'react';
import { Bell, ChevronDown, LogOut, User, Settings } from 'lucide-react';
import { useUser, useClerk } from '@clerk/clerk-react';

const Header: React.FC = () => {
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const { user } = useUser();
  const { signOut } = useClerk();

  const handleSignOut = () => {
    signOut();
  };

  return (
    <header className="h-16 bg-white border-b border-gray-200">
      <div className="h-full px-6 flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-gray-800">Dashboard</h2>
        </div>
        
        <div className="flex items-center space-x-4">
          <button className="p-2 text-gray-600 hover:text-gray-900 rounded-lg hover:bg-gray-50">
            <Bell size={20} />
          </button>
          
          <div className="relative">
            <button
              onClick={() => setIsDropdownOpen(!isDropdownOpen)}
              className="flex items-center space-x-2 p-2 rounded-lg hover:bg-gray-50"
            >
              <div className="w-8 h-8 bg-primary-100 rounded-full flex items-center justify-center">
                {user?.imageUrl ? (
                  <img
                    src={user.imageUrl}
                    alt={`${user.fullName || 'User'}'s profile`}
                    className="w-8 h-8 rounded-full"
                  />
                ) : (
                  <User size={20} className="text-primary-600" />
                )}
              </div>
              <span className="text-sm font-medium text-gray-700">
                {user?.fullName || 'User'}
              </span>
              <ChevronDown size={16} className="text-gray-500" />
            </button>

            {isDropdownOpen && (
              <div className="absolute right-0 mt-2 w-48 bg-white rounded-lg shadow-soft border border-gray-100 py-1">
                <button
                  onClick={() => {/* Add profile action */}}
                  className="flex items-center space-x-2 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 w-full text-left"
                >
                  <Settings size={16} />
                  <span>Profile Settings</span>
                </button>
                <button
                  onClick={handleSignOut}
                  className="flex items-center space-x-2 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 w-full text-left"
                >
                  <LogOut size={16} />
                  <span>Sign Out</span>
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
};

export default Header; 