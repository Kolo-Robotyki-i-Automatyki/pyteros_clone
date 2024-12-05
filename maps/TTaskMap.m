function TTaskMap
close all;

%% option #1
d = importdata('DTM_ver1.csv');
x = d.data(:,1);
y = d.data(:,2);
h = d.data(:,3);

dx = unique(x); dx = dx(2)-dx(1);
dy = unique(y); dy = dy(2)-dy(1);
mxX = max(x);
mxY = max(y);
mnX = min(x);
mnY = min(y);
[xq,yq] = meshgrid(mnX:dx:mxX, mnY:dy:mxY);
map = griddata(x,y,h,xq,yq,'cubic');
% -------------------------------------------------------------------------

%% option #2
% d = importdata('DTM_ver2.csv');
% map = flipud(d.data);
% q = str2num(d.textdata{2});
% dx = q(3);
% dy = q(4);
% mnX = q(5);
% mxX = mnX + dx*(q(2)-1);
% mxY = q(6);
% mnY = mxY - dy*(q(1)-1);
% [xq,yq] = meshgrid(mnX:dx:mxX, mnY:dy:mxY);
% -------------------------------------------------------------------------

figure('Position',[100 300 1000 530]);
axes('Position',[0.06,0.1,0.90,0.85]);
pcolor(xq,yq, map);
colormap(jet);
hold on;
addPoints();
addDescription();

figure('Position',[200 200 1000 530]);
axes('Position',[0.06,0.1,0.90,0.85]);
contour(xq,yq, map);
set(gca,'XTick',0:2:mxX,'YTick',0:2:mxY);
grid
colormap(jet);
axis equal;
hold on;
addPoints();
addDescription();

end

function addPoints
    d = importdata('Landmarks.csv');
    n = d.textdata(2:end,1);
    x = d.data(:,1);
    y = d.data(:,2);
    plot(x,y,'g.','MarkerSize',25);
    text(x,y+1,n,'Horizontalalignment','center');

    d = importdata('Waypoints.csv');
    n = d.textdata(2:end,1);
    x = d.data(:,1);
    y = d.data(:,2);
    plot(x,y,'r.','MarkerSize',25);
    text(x,y+1,n,'Horizontalalignment','center');
end

function addDescription
    hc = colorbar;
    xlabel('[m]');
    ylabel('[m]');
    title('ERC 2018 - traversal task (example!)');
    title(hc,'height [m]');
end
