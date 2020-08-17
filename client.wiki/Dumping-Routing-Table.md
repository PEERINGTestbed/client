
Adding the following lines to bird.conf file can dump the routing table in filename directory. It will periodically dump the routing table in every 300s in mrt format. You can change the directory and period if you want.

```
protocol mrt {
	table rtup;
	where source = RTS_BGP;
	filename "/dir/out.mrt";
	period 300;
}
```
